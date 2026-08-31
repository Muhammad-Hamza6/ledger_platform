# apps/subscriptions/tests/test_tasks.py

import uuid
from datetime import timedelta
from decimal import Decimal
from threading import Barrier, Thread
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.ledger.models import Account, LedgerEntry, Transaction
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.subscriptions.tasks import (
    charge_single_subscription,
    process_subscription_renewals,
)

User = get_user_model()


class SubscriptionTaskTestMixin:
    """Shared setup for platform account + a funded subscriber, since both
    task test classes need identical fixtures."""

    def _create_platform_account(self):
        system_user, _ = User.objects.get_or_create(
            email="platform-system@internal.ledgerplatform",
            defaults={"is_active": True},
        )
        account, _ = Account.objects.get_or_create(
            id=settings.PLATFORM_REVENUE_ACCOUNT_ID,
            defaults={
                "owner": system_user,
                "name": "platform_revenue",
                "currency": "USD",
            },
        )
        return account

    def _create_funded_subscription(
        self, status=None, next_renewal_at=None, balance=Decimal("50.00")
    ):
        user = User.objects.create_user(
            email=f"subscriber_{uuid.uuid4()}@example.com", password="password123"
        )
        account = Account.objects.create(owner=user, name="wallet", currency="USD")
        plan = SubscriptionPlan.objects.create(
            name="Pro Monthly",
            price=Decimal("9.99"),
            currency="USD",
            interval_days=SubscriptionPlan.IntervalDays.MONTHLY,
        )
        if balance > 0:
            funding_tx = Transaction.objects.create(description="Test funding")
            LedgerEntry.objects.create(
                transaction=funding_tx,
                account=account,
                amount=balance,
                direction=LedgerEntry.Direction.CREDIT,
            )
        subscription = Subscription.objects.create(
            user=user,
            account=account,
            plan=plan,
            status=status or Subscription.Status.ACTIVE,
            next_renewal_at=next_renewal_at or (timezone.now() - timedelta(hours=1)),
        )
        return subscription


class ChargeSingleSubscriptionTest(SubscriptionTaskTestMixin, TestCase):
    def setUp(self):
        self.platform_account = self._create_platform_account()

    def test_successful_charge_advances_next_renewal_at(self):
        subscription = self._create_funded_subscription(balance=Decimal("50.00"))
        original_renewal_date = subscription.next_renewal_at

        charge_single_subscription(subscription.id)

        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.Status.ACTIVE)
        self.assertEqual(
            subscription.next_renewal_at,
            original_renewal_date + timedelta(days=subscription.plan.interval_days),
        )

    def test_successful_charge_recovers_past_due_status(self):
        subscription = self._create_funded_subscription(
            status=Subscription.Status.PAST_DUE, balance=Decimal("50.00")
        )
        charge_single_subscription(subscription.id)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.Status.ACTIVE)

    def test_insufficient_funds_marks_past_due_without_advancing_date(self):
        subscription = self._create_funded_subscription(balance=Decimal("0.00"))
        original_renewal_date = subscription.next_renewal_at

        charge_single_subscription(subscription.id)

        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.Status.PAST_DUE)
        self.assertEqual(subscription.next_renewal_at, original_renewal_date)

    def test_cancelled_subscription_is_skipped_without_error(self):
        subscription = self._create_funded_subscription(
            status=Subscription.Status.CANCELLED, balance=Decimal("50.00")
        )
        # Should not raise — InvalidSubscriptionStateError is caught and
        # logged inside the task, not propagated.
        charge_single_subscription(subscription.id)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, Subscription.Status.CANCELLED)

    def test_charging_creates_exactly_one_balanced_transaction(self):
        subscription = self._create_funded_subscription(balance=Decimal("50.00"))
        charge_single_subscription(subscription.id)

        entries = LedgerEntry.objects.filter(account=subscription.account)
        debit_entries = entries.filter(direction=LedgerEntry.Direction.DEBIT)
        self.assertEqual(debit_entries.count(), 1)
        self.assertEqual(debit_entries.first().amount, subscription.plan.price)


class RenewalLockConcurrencyTest(SubscriptionTaskTestMixin, TransactionTestCase):
    def test_concurrent_renewal_attempts_only_charge_once(self):
        """
        Proves the Redis distributed lock actually prevents the same
        subscription from being charged twice if charge_single_subscription
        somehow gets triggered concurrently (e.g. a duplicate Beat firing).
        Mirrors the same Barrier-based pattern as the ledger transfer
        concurrency test.
        """
        platform_account = self._create_platform_account()
        subscription = self._create_funded_subscription(balance=Decimal("50.00"))

        barrier = Barrier(2)
        results = []

        def worker():
            barrier.wait()
            try:
                charge_single_subscription(subscription.id)
                results.append("ran")
            except Exception as e:  # noqa: BLE001
                results.append(f"error: {type(e).__name__}: {e}")
            finally:
                connection.close()

        thread1 = Thread(target=worker)
        thread2 = Thread(target=worker)
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        print(f"Results of concurrent renewal attempts: {results}")

        # Both threads should complete without error (one charges, one
        # skips because the lock is held) — but only ONE debit should
        # actually exist on the account afterward.
        subscription.refresh_from_db()
        debit_count = LedgerEntry.objects.filter(
            account=subscription.account,
            direction=LedgerEntry.Direction.DEBIT,
        ).count()
        self.assertEqual(
            debit_count,
            1,
            f"Expected exactly one charge despite concurrent attempts, "
            f"got {debit_count}. Results: {results}",
        )


class ProcessSubscriptionRenewalsTest(SubscriptionTaskTestMixin, TestCase):
    def setUp(self):
        self.platform_account = self._create_platform_account()

    def test_dispatches_one_task_per_due_subscription(self):
        due_1 = self._create_funded_subscription(balance=Decimal("50.00"))
        due_2 = self._create_funded_subscription(balance=Decimal("50.00"))
        not_due = self._create_funded_subscription(
            balance=Decimal("50.00"),
            next_renewal_at=timezone.now() + timedelta(days=10),
        )

        with patch(
            "apps.subscriptions.tasks.charge_single_subscription.delay"
        ) as mock_delay:
            count = process_subscription_renewals()

        self.assertEqual(count, 2)
        dispatched_ids = {call.args[0] for call in mock_delay.call_args_list}
        self.assertEqual(dispatched_ids, {due_1.id, due_2.id})
        self.assertNotIn(not_due.id, dispatched_ids)

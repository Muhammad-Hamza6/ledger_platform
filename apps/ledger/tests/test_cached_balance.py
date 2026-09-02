from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ledger.models import Account, LedgerEntry, Transaction
from apps.ledger.selectors.account import get_account_balance
from apps.ledger.services.transfer import transfer_funds

User = get_user_model()


class CachedBalanceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="cache_test@example.com", password="password123"
        )
        self.sender = Account.objects.create(
            owner=self.user, name="sender", currency="USD"
        )
        self.receiver = Account.objects.create(
            owner=self.user, name="receiver", currency="USD"
        )
        funding_tx = Transaction.objects.create(description="Initial funding")
        LedgerEntry.objects.create(
            transaction=funding_tx,
            account=self.sender,
            amount=Decimal("100.00"),
            direction=LedgerEntry.Direction.CREDIT,
        )
        self.sender.cached_balance = Decimal("100.00")
        self.sender.save(update_fields=["cached_balance"])

    def test_cached_balance_matches_derived_balance_after_transfer(self):
        transfer_funds(
            from_account=self.sender.id,
            to_account=self.receiver.id,
            amount=Decimal("30.00"),
            idempotency_key="cache-test-001",
        )

        self.sender.refresh_from_db()
        self.receiver.refresh_from_db()

        derived_sender_balance = get_account_balance(self.sender.id)
        derived_receiver_balance = get_account_balance(self.receiver.id)

        self.assertEqual(self.sender.cached_balance, derived_sender_balance)
        self.assertEqual(self.receiver.cached_balance, derived_receiver_balance)
        self.assertEqual(self.sender.cached_balance, Decimal("70.00"))
        self.assertEqual(self.receiver.cached_balance, Decimal("30.00"))

    def test_cached_balance_stays_correct_across_multiple_transfers(self):
        """Proves the cache doesn't drift over several sequential operations,
        not just a single one."""
        transfer_funds(
            from_account=self.sender.id,
            to_account=self.receiver.id,
            amount=Decimal("10.00"),
            idempotency_key="multi-1",
        )
        transfer_funds(
            from_account=self.sender.id,
            to_account=self.receiver.id,
            amount=Decimal("15.00"),
            idempotency_key="multi-2",
        )
        transfer_funds(
            from_account=self.receiver.id,
            to_account=self.sender.id,
            amount=Decimal("5.00"),
            idempotency_key="multi-3",
        )

        self.sender.refresh_from_db()
        self.receiver.refresh_from_db()

        self.assertEqual(
            self.sender.cached_balance, get_account_balance(self.sender.id)
        )
        self.assertEqual(
            self.receiver.cached_balance, get_account_balance(self.receiver.id)
        )

# apps/subscriptions/tests/test_models.py

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.ledger.models import Account
from apps.subscriptions.models import Subscription, SubscriptionPlan

User = get_user_model()


class SubscriptionPlanTest(TestCase):
    def setUp(self):
        self.monthly_plan = SubscriptionPlan.objects.create(
            name="Pro Monthly",
            price=Decimal("9.99"),
            currency="USD",
            interval_days=SubscriptionPlan.IntervalDays.MONTHLY,
        )

    def test_plan_str_representation(self):
        """Test that __str__ returns a human-readable summary, not None."""
        self.assertIn("Pro Monthly", str(self.monthly_plan))
        self.assertIn("9.99", str(self.monthly_plan))

    def test_plan_created_with_correct_defaults(self):
        """Test that is_active defaults to True on creation."""
        self.assertTrue(self.monthly_plan.is_active)

    def test_invalid_interval_days_rejected_by_constraint(self):
        """Test that the DB-level CheckConstraint rejects any interval_days
        value outside the allowed set (30, 365), even bypassing choices=
        validation by calling .create() directly."""
        with self.assertRaises(IntegrityError):
            SubscriptionPlan.objects.create(
                name="Bad Plan",
                price=Decimal("1.00"),
                currency="USD",
                interval_days=17,
            )

    def test_yearly_interval_is_accepted(self):
        """Test that the other valid choice (365) is accepted without error."""
        yearly_plan = SubscriptionPlan.objects.create(
            name="Pro Yearly",
            price=Decimal("99.00"),
            currency="USD",
            interval_days=SubscriptionPlan.IntervalDays.YEARLY,
        )
        self.assertEqual(yearly_plan.interval_days, 365)


class SubscriptionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="subscriber@example.com", password="password123"
        )
        self.account = Account.objects.create(
            owner=self.user, name="wallet", currency="USD"
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Pro Monthly",
            price=Decimal("9.99"),
            currency="USD",
            interval_days=SubscriptionPlan.IntervalDays.MONTHLY,
        )

    def test_subscription_created_with_active_status_by_default(self):
        """Test that a new Subscription defaults to ACTIVE status."""
        subscription = Subscription.objects.create(
            user=self.user,
            account=self.account,
            plan=self.plan,
            next_renewal_at=timezone.now() + timedelta(days=self.plan.interval_days),
        )
        self.assertEqual(subscription.status, Subscription.Status.ACTIVE)

    def test_subscription_str_representation(self):
        """Test that __str__ includes user and plan info, not None."""
        subscription = Subscription.objects.create(
            user=self.user,
            account=self.account,
            plan=self.plan,
            next_renewal_at=timezone.now() + timedelta(days=self.plan.interval_days),
        )
        self.assertIn(self.plan.name, str(subscription))
        self.assertNotEqual(str(subscription), "None")

    def test_subscription_relationships_traverse_correctly(self):
        """Test that related_name accessors work as expected on all three FKs."""
        subscription = Subscription.objects.create(
            user=self.user,
            account=self.account,
            plan=self.plan,
            next_renewal_at=timezone.now() + timedelta(days=self.plan.interval_days),
        )
        self.assertIn(subscription, self.user.subscriptions.all())
        self.assertIn(subscription, self.account.account_subscriptions.all())
        self.assertIn(subscription, self.plan.plan_subscriptions.all())

    def test_cancelled_at_is_null_until_explicitly_cancelled(self):
        """Test that cancelled_at stays null on creation, since it's only
        set when a subscription is actually cancelled (a later service-layer
        concern, not model-level behavior)."""
        subscription = Subscription.objects.create(
            user=self.user,
            account=self.account,
            plan=self.plan,
            next_renewal_at=timezone.now() + timedelta(days=self.plan.interval_days),
        )
        self.assertIsNone(subscription.cancelled_at)

    def test_deleting_referenced_plan_is_protected(self):
        """Test that on_delete=PROTECT prevents deleting a SubscriptionPlan
        that still has an active Subscription referencing it — mirrors the
        same protection already proven on Account.owner in ledger tests."""
        Subscription.objects.create(
            user=self.user,
            account=self.account,
            plan=self.plan,
            next_renewal_at=timezone.now() + timedelta(days=self.plan.interval_days),
        )
        with self.assertRaises(  # noqa: B017
            Exception
        ):  # django.db.models.ProtectedError
            self.plan.delete()

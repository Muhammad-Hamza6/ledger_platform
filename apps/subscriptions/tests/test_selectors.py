# apps/subscriptions/tests/test_selectors.py

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.ledger.models import Account
from apps.subscriptions.models import Subscription, SubscriptionPlan
from apps.subscriptions.selectors.subscription import get_due_subscriptions

User = get_user_model()


class GetDueSubscriptionsTest(TestCase):
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
        self.now = timezone.now()

    def _create_subscription(self, status, next_renewal_at):
        return Subscription.objects.create(
            user=self.user,
            account=self.account,
            plan=self.plan,
            status=status,
            next_renewal_at=next_renewal_at,
        )

    def test_active_subscription_past_due_date_is_included(self):
        sub = self._create_subscription(
            Subscription.Status.ACTIVE, self.now - timedelta(days=1)
        )
        self.assertIn(sub, get_due_subscriptions(now=self.now))

    def test_past_due_subscription_is_included(self):
        sub = self._create_subscription(
            Subscription.Status.PAST_DUE, self.now - timedelta(days=1)
        )
        self.assertIn(sub, get_due_subscriptions(now=self.now))

    def test_active_subscription_not_yet_due_is_excluded(self):
        sub = self._create_subscription(
            Subscription.Status.ACTIVE, self.now + timedelta(days=5)
        )
        self.assertNotIn(sub, get_due_subscriptions(now=self.now))

    def test_cancelled_subscription_is_excluded_even_if_overdue(self):
        sub = self._create_subscription(
            Subscription.Status.CANCELLED, self.now - timedelta(days=1)
        )
        self.assertNotIn(sub, get_due_subscriptions(now=self.now))

    def test_expired_subscription_is_excluded(self):
        sub = self._create_subscription(
            Subscription.Status.EXPIRED, self.now - timedelta(days=1)
        )
        self.assertNotIn(sub, get_due_subscriptions(now=self.now))

    def test_subscription_due_exactly_now_is_included(self):
        """Boundary check: next_renewal_at == now should count as due
        (uses __lte, not __lt)."""
        sub = self._create_subscription(Subscription.Status.ACTIVE, self.now)
        self.assertIn(sub, get_due_subscriptions(now=self.now))

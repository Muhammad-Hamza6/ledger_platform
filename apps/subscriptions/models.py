import uuid

from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Q

from apps.ledger.models import Account

user_model = settings.AUTH_USER_MODEL


class SubscriptionPlan(models.Model):
    class IntervalDays(models.IntegerChoices):
        MONTHLY = 30, "Monthly"
        YEARLY = 365, "Yearly"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=19, decimal_places=4)
    currency = models.CharField(max_length=3)
    interval_days = models.PositiveIntegerField(
        choices=IntervalDays.choices,
        help_text="Number of days between renewals, e.g. 30 for monthly, 365 for yearly.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.price} {self.currency} / {self.interval_days}d)"

    class Meta:
        constraints = [  # noqa: RUF012
            CheckConstraint(
                check=Q(interval_days__in=[30, 365]),
                name="valid_interval_days",
            )
        ]


class Subscription(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        user_model, on_delete=models.PROTECT, related_name="subscriptions"
    )
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="account_subscriptions"
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name="plan_subscriptions"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    next_renewal_at = models.DateTimeField()
    started_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} → {self.plan.name} ({self.status})"

import uuid

from django.conf import settings
from django.db import models


class SubscriptionPlan(models.Model):
    class Interval_Days(models.IntegerChoices):
        MONTHLY = 30, "Monthly"
        YEARLY = 365, "Yearly"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=19, decimal_places=4)
    currency = models.CharField(max_length=3)
    interval_days = models.PositiveIntegerField(
        choices=Interval_Days.choices,
        help_text="Number of days between renewals, e.g. 30 for monthly, 365 for yearly.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.price} {self.currency} / {self.interval_days}d)"

    class Meta:
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                check=models.Q(interval_days__in=[30, 365]),
                name="valid_interval_days",
            )
        ]

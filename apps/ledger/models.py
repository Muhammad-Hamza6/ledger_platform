import uuid

from django.conf import settings
from django.db import models
from django.db.models import CheckConstraint, Q


# Create your models here.
class Account(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="accounts"
    )
    name = models.CharField(max_length=50)
    currency = models.CharField(max_length=3)
    allows_overdraft = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.currency}) - {self.owner}"


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        TRANSFER = "transfer", "Transfer"
        SUBSCRIPTION_RENEWAL = "subscription_renewal", "Subscription Renewal"
        REVERSAL = "reversal", "Reversal"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REVERSED = "reversed", "Reversed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.CharField(
        max_length=255, unique=True, null=True, blank=True
    )
    transaction_type = models.CharField(
        max_length=50, choices=TransactionType.choices, default=TransactionType.TRANSFER
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.COMPLETED
    )
    description = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reversed_transaction = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversals",
    )

    def __str__(self):
        return f"Transaction {self.id} [{self.status}]"


class LedgerEntry(models.Model):
    class Direction(models.TextChoices):
        DEBIT = "debit", "Debit"
        CREDIT = "credit", "Credit"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        Transaction, on_delete=models.PROTECT, related_name="entries"
    )
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="ledger_entries"
    )
    amount = models.DecimalField(max_digits=19, decimal_places=4)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [  # noqa: RUF012
            CheckConstraint(
                condition=Q(amount__gt=0), name="ledger_entry_amount_gt_zero"
            )
        ]

    def __str__(self):
        return f"{self.direction.upper()} {self.amount} for Account {self.account_id}"

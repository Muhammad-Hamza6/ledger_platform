from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from apps.ledger.models import LedgerEntry


def get_account_balance(account_id: str) -> Decimal:
    """Calculates the balance: total credits - total debits."""

    result = LedgerEntry.objects.filter(account_id=account_id).aggregate(
        total_credits=Coalesce(
            Sum("amount", filter=Q(direction="credit")), Decimal("0.00")
        ),
        total_debits=Coalesce(
            Sum("amount", filter=Q(direction="debit")), Decimal("0.00")
        ),
    )

    return result["total_credits"] - result["total_debits"]

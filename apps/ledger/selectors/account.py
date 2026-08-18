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


def get_account_transactions(
    account_id, start_date=None, end_date=None, limit=None, offset=None
):
    """Fetches optimized ledger entries for an account with date filtering and pagination."""
    queryset = (
        LedgerEntry.objects.select_related("account", "transaction")
        .filter(account_id=account_id)
        .order_by("-created_at")
    )

    if start_date:
        queryset = queryset.filter(created_at__gte=start_date)

    if end_date:
        queryset = queryset.filter(created_at__lte=end_date)

    if limit is not None:
        start = offset if offset is not None else 0
        queryset = queryset[start : start + limit]
    elif offset is not None:
        queryset = queryset[offset:]

    return queryset

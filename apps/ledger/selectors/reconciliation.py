# apps/ledger/selectors/reconciliation.py

from apps.ledger.models import Account
from apps.ledger.selectors.account import get_account_balance


def find_balance_discrepancies(account_queryset=None):
    """
    Compares each account's cached_balance against its derived balance
    (computed fresh from LedgerEntry rows). Returns a list of dicts, one
    per account where they disagree.

    Purely detection — does not create records, fix anything, or decide
    severity. account_queryset lets callers scope this to a subset
    (useful for batching large datasets or targeted testing).
    """
    accounts = (
        account_queryset if account_queryset is not None else Account.objects.all()
    )

    discrepancies = []
    for account in accounts.iterator():
        derived_balance = get_account_balance(account.id)
        if account.cached_balance != derived_balance:
            discrepancies.append(
                {
                    "account_id": account.id,
                    "cached_balance": account.cached_balance,
                    "derived_balance": derived_balance,
                    "discrepancy_amount": derived_balance - account.cached_balance,
                }
            )

    return discrepancies

# apps/ledger/services/reconciliation.py

from apps.ledger.models import BalanceDiscrepancy
from apps.ledger.selectors.reconciliation import find_balance_discrepancies


def run_balance_reconciliation():
    """
    Runs the discrepancy check across all accounts and records any newly
    found issues. Deliberately does NOT auto-correct cached_balance — if
    the cache disagrees with the ledger, we don't know which one is
    actually wrong without investigation, so this function only detects
    and records, never "fixes."

    Skip-if-unresolved-exists: if an account already has an unresolved
    BalanceDiscrepancy record, this run does not create a duplicate —
    otherwise a persistent, unfixed bug would create a new row every
    single day forever, which is noise rather than signal. The existing
    unresolved record already represents "this account needs attention";
    a human resolving it is what should trigger a fresh check next time.
    """
    discrepancies = find_balance_discrepancies()

    accounts_checked = _count_accounts_checked()
    newly_recorded = 0
    skipped_existing = 0

    for discrepancy in discrepancies:
        already_unresolved = BalanceDiscrepancy.objects.filter(
            account_id=discrepancy["account_id"],
            resolved_at__isnull=True,
        ).exists()

        if already_unresolved:
            skipped_existing += 1
            continue

        BalanceDiscrepancy.objects.create(
            account_id=discrepancy["account_id"],
            cached_balance_at_check=discrepancy["cached_balance"],
            derived_balance_at_check=discrepancy["derived_balance"],
            discrepancy_amount=discrepancy["discrepancy_amount"],
        )
        newly_recorded += 1

    return {
        "accounts_checked": accounts_checked,
        "discrepancies_found": len(discrepancies),
        "newly_recorded": newly_recorded,
        "skipped_existing_unresolved": skipped_existing,
    }


def _count_accounts_checked():
    from apps.ledger.models import Account

    return Account.objects.count()

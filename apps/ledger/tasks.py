import logging

from celery import shared_task

from apps.ledger.services.reconciliation import run_balance_reconciliation

logger = logging.getLogger(__name__)


@shared_task
def reconcile_account_balances():
    """
    Scheduled entry point (daily, via Celery Beat) for balance
    reconciliation. Alerting on discrepancies (email/Slack) is
    deliberately out of scope here — that's Sprint 7 (observability)
    territory. This task's job is detection and recording only.
    """
    summary = run_balance_reconciliation()
    logger.info(
        "Reconciliation complete: checked=%d found=%d recorded=%d skipped=%d",
        summary["accounts_checked"],
        summary["discrepancies_found"],
        summary["newly_recorded"],
        summary["skipped_existing_unresolved"],
    )
    return summary

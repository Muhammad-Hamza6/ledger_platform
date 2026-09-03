# apps/ledger/tests/test_reconciliation.py

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ledger.models import Account, BalanceDiscrepancy, LedgerEntry, Transaction
from apps.ledger.services.reconciliation import run_balance_reconciliation

User = get_user_model()


class ReconciliationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="recon_test@example.com", password="password123"
        )
        self.account = Account.objects.create(
            owner=self.user, name="checking", currency="USD"
        )
        funding_tx = Transaction.objects.create(description="Funding")
        LedgerEntry.objects.create(
            transaction=funding_tx,
            account=self.account,
            amount=Decimal("100.00"),
            direction=LedgerEntry.Direction.CREDIT,
        )
        # Correctly synced cache — simulates normal operation via transfer_funds()
        self.account.cached_balance = Decimal("100.00")
        self.account.save(update_fields=["cached_balance"])

    def test_no_discrepancy_recorded_when_cache_is_correct(self):
        summary = run_balance_reconciliation()
        self.assertEqual(summary["discrepancies_found"], 0)
        self.assertEqual(
            BalanceDiscrepancy.objects.filter(account=self.account).count(), 0
        )

    def test_discrepancy_detected_when_cache_is_manually_desynced(self):
        """
        Deliberately bypasses the service layer to simulate the exact
        scenario reconciliation exists to catch — a bug, manual DB edit,
        or migration mistake that leaves cached_balance wrong.
        """
        self.account.cached_balance = Decimal("999.99")
        self.account.save(update_fields=["cached_balance"])

        summary = run_balance_reconciliation()

        self.assertEqual(summary["discrepancies_found"], 1)
        self.assertEqual(summary["newly_recorded"], 1)

        discrepancy = BalanceDiscrepancy.objects.get(account=self.account)
        self.assertEqual(discrepancy.cached_balance_at_check, Decimal("999.99"))
        self.assertEqual(discrepancy.derived_balance_at_check, Decimal("100.00"))
        self.assertEqual(discrepancy.discrepancy_amount, Decimal("-899.99"))
        self.assertIsNone(discrepancy.resolved_at)

    def test_running_reconciliation_twice_does_not_duplicate_unresolved_discrepancy(
        self,
    ):
        self.account.cached_balance = Decimal("999.99")
        self.account.save(update_fields=["cached_balance"])

        run_balance_reconciliation()
        summary_second_run = run_balance_reconciliation()

        self.assertEqual(summary_second_run["newly_recorded"], 0)
        self.assertEqual(summary_second_run["skipped_existing_unresolved"], 1)
        self.assertEqual(
            BalanceDiscrepancy.objects.filter(account=self.account).count(), 1
        )

    def test_new_discrepancy_recorded_after_previous_one_resolved(self):
        """Proves skip-if-unresolved is scoped to UNRESOLVED specifically,
        not 'ever had a discrepancy' — a resolved issue shouldn't block
        detection of a fresh, later problem."""
        self.account.cached_balance = Decimal("999.99")
        self.account.save(update_fields=["cached_balance"])
        run_balance_reconciliation()

        old_discrepancy = BalanceDiscrepancy.objects.get(account=self.account)
        old_discrepancy.resolved_at = old_discrepancy.detected_at
        old_discrepancy.resolution_notes = "Investigated, was a test artifact"
        old_discrepancy.save()

        # Cache is still wrong (nothing auto-corrected it — by design),
        # so a fresh run should record a NEW discrepancy since the old
        # one is now resolved.
        summary = run_balance_reconciliation()
        self.assertEqual(summary["newly_recorded"], 1)
        self.assertEqual(
            BalanceDiscrepancy.objects.filter(account=self.account).count(), 2
        )

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ledger.models import Account, LedgerEntry, Transaction

User = get_user_model()


class LedgerInvariantTest(TestCase):
    def setUp(self):
        # Create a user and two accounts (e.g., Checking and Wallet)
        self.user = User.objects.create_user(
            email="ledger_user@example.com", password="password123"
        )
        self.account_a = Account.objects.create(
            owner=self.user, name="checking", currency="USD"
        )
        self.account_b = Account.objects.create(
            owner=self.user, name="wallet", currency="USD"
        )

    def test_transaction_balance_invariant(self):
        """Test that a valid transaction has equal total debits and credits."""
        # 1. Create a Transaction container
        txn = Transaction.objects.create(
            transaction_type=Transaction.TransactionType.TRANSFER,
            status=Transaction.Status.COMPLETED,
        )

        amount = Decimal("100.00")

        # 2. Create balanced entries: Debit Account A, Credit Account B
        LedgerEntry.objects.create(
            transaction=txn,
            account=self.account_a,
            amount=amount,
            direction=LedgerEntry.Direction.DEBIT,
        )
        LedgerEntry.objects.create(
            transaction=txn,
            account=self.account_b,
            amount=amount,
            direction=LedgerEntry.Direction.CREDIT,
        )

        # 3. Calculate sums for verification
        total_debits = sum(
            entry.amount
            for entry in txn.entries.filter(direction=LedgerEntry.Direction.DEBIT)
        )
        total_credits = sum(
            entry.amount
            for entry in txn.entries.filter(direction=LedgerEntry.Direction.CREDIT)
        )

        # 4. Assert the core invariant
        self.assertEqual(total_debits, total_credits)

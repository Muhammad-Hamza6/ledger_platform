import uuid
from decimal import Decimal
from threading import Barrier, Thread

from django.test import TransactionTestCase

from apps.ledger.models import Account, LedgerEntry, Transaction
from apps.ledger.services.transfer import transfer_funds
from apps.users.models import User
from common.exceptions import InsufficientFundsError


class ConcurrencyTransferTestCase(TransactionTestCase):
    def test_concurrent_transfers_prevent_overdraft(self):
        # 1. Create user
        user1 = User.objects.create_user(
            email="test@example.com", password="securepassword123"
        )
        user2 = User.objects.create_user(
            email="test1@email.com", password="securepassword123"
        )
        # 2. Create accounts
        sender = Account.objects.create(
            name="Sender Account", owner=user1, currency="USD"
        )
        receiver = Account.objects.create(
            name="Receiver Account", owner=user2, currency="USD"
        )

        # 3. Seed initial balance ($50) via a funding transaction and credit entry
        funding_tx = Transaction.objects.create(description="Initial funding")
        LedgerEntry.objects.create(
            transaction=funding_tx,
            account=sender,
            amount=Decimal("50.00"),
            direction=LedgerEntry.Direction.CREDIT,
        )

        # 4. Initialize a barrier for 2 threads to ensure simultaneous execution
        barrier = Barrier(2)
        results = []

        def worker():
            barrier.wait()
            try:
                transfer_funds(
                    from_account=sender.id,
                    to_account=receiver.id,
                    amount=Decimal("30.00"),
                    idempotency_key=uuid.uuid4(),
                )
                results.append("success")
            except InsufficientFundsError:
                results.append("insufficient_funds")
            except Exception as e:
                results.append(f"error: {type(e).__name__}: {e}")

        # 5. Create and start both threads 🧵
        thread1 = Thread(target=worker)
        thread2 = Thread(target=worker)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        print("\nTHREAD RESULTS:", results)
        # 6. Assertions: exactly one succeeds, one fails
        self.assertEqual(results.count("success"), 1)
        self.assertEqual(results.count("insufficient_funds"), 1)

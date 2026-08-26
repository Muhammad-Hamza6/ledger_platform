import uuid
from decimal import Decimal
from threading import Barrier, Thread

from django.db import connection
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
            except Exception as e:  # noqa: BLE001
                results.append(f"error: {type(e).__name__}: {e}")

        # 5. Create and start both threads 🧵
        thread1 = Thread(target=worker)
        thread2 = Thread(target=worker)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        print(f"Results of concurrent transfers: {results}")
        # 6. Assertions: exactly one succeeds, one fails
        self.assertEqual(results.count("success"), 1)
        self.assertEqual(results.count("insufficient_funds"), 1)

    def test_concurrent_duplicate_idempotency_key_creates_only_one_transaction(self):
        # 1. Create users and accounts
        user1 = User.objects.create_user(
            email="idem_sender@example.com", password="securepassword123"
        )
        user2 = User.objects.create_user(
            email="idem_receiver@example.com", password="securepassword123"
        )
        sender = Account.objects.create(
            name="Idempotency Sender", owner=user1, currency="USD"
        )
        receiver = Account.objects.create(
            name="Idempotency Receiver", owner=user2, currency="USD"
        )

        # 2. Seed sender with enough balance that BOTH threads could
        #    plausibly succeed on funds alone — this isolates the test
        #    to the idempotency guarantee specifically, not overdraft
        #    protection (which is already covered by the other test).
        funding_tx = Transaction.objects.create(description="Initial funding")
        LedgerEntry.objects.create(
            transaction=funding_tx,
            account=sender,
            amount=Decimal("500.00"),
            direction=LedgerEntry.Direction.CREDIT,
        )

        # 3. Same idempotency key for BOTH threads — this is the whole point
        shared_idempotency_key = str(uuid.uuid4())

        barrier = Barrier(2)
        results = []

        def worker():
            barrier.wait()
            try:
                txn = transfer_funds(
                    from_account=sender.id,
                    to_account=receiver.id,
                    amount=Decimal("30.00"),
                    idempotency_key=shared_idempotency_key,
                )
                results.append(("success", txn.id))
            except Exception as e:  # noqa: BLE001
                results.append((f"error: {type(e).__name__}", str(e)))
            finally:
                # Each thread needs its own DB connection closed explicitly
                # when running raw threads (not Django's test client) against
                # TransactionTestCase, to avoid connection leakage across threads.
                connection.close()

        thread1 = Thread(target=worker)
        thread2 = Thread(target=worker)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        print(f"Results of concurrent idempotent transfers: {results}")

        # 4. Both threads should report success (one creates the transaction,
        #    the other catches IntegrityError and returns the same one)
        self.assertEqual(
            [r[0] for r in results],
            ["success", "success"],
            f"Expected both threads to succeed (one creating, one returning "
            f"the existing transaction), got: {results}",
        )

        # 5. Both threads must have returned the SAME transaction ID
        transaction_ids = {r[1] for r in results}
        self.assertEqual(
            len(transaction_ids),
            1,
            f"Expected both threads to return the same transaction ID, "
            f"got different IDs: {transaction_ids}",
        )

        # 6. The real proof: only ONE Transaction row exists in the DB
        #    with this idempotency key, and only ONE pair of LedgerEntry
        #    rows resulted from it — not two.
        matching_transactions = Transaction.objects.filter(
            idempotency_key=shared_idempotency_key
        )
        self.assertEqual(
            matching_transactions.count(),
            1,
            "Duplicate idempotency key must not create more than one Transaction.",
        )

        entries_for_this_transaction = LedgerEntry.objects.filter(
            transaction=matching_transactions.first()
        )
        self.assertEqual(
            entries_for_this_transaction.count(),
            2,
            "Exactly one debit + one credit entry should exist, not four "
            "(which would indicate the transfer ran twice).",
        )

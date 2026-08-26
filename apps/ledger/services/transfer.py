from django.db import IntegrityError, transaction
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from apps.ledger.models import Account, LedgerEntry, Transaction
from common.exceptions import InsufficientFundsError, InvalidAmountError


def transfer_funds(from_account, to_account, amount, idempotency_key, description=None):

    # Fast-path check: catches the common case (client retry after receiving
    # a successful response) without needing a lock. This does NOT fully
    # protect against a genuine race — the try/except IntegrityError below
    # is what actually guarantees correctness under concurrency.
    existing_transaction = Transaction.objects.filter(
        idempotency_key=idempotency_key
    ).first()
    if existing_transaction is not None:
        return existing_transaction

    if amount <= 0:
        raise InvalidAmountError(amount=amount)

    # Ensure we have the account IDs whether instances or UUIDs were passed
    from_id = from_account.id if isinstance(from_account, Account) else from_account
    to_id = to_account.id if isinstance(to_account, Account) else to_account

    # Sort account IDs to prevent deadlocks (consistent lock ordering requirement)
    first_id, second_id = sorted([from_id, to_id])

    try:
        with transaction.atomic():
            # Lock accounts in consistent order — keep the locked instances,
            # don't re-query afterward (avoids two redundant unlocked reads).
            first_account = Account.objects.select_for_update(of=("self",)).get(
                id=first_id
            )
            second_account = Account.objects.select_for_update(of=("self",)).get(
                id=second_id
            )

            sender = first_account if first_account.id == from_id else second_account
            receiver = second_account if second_account.id == to_id else first_account

            # Calculate sender's balance dynamically (Credits - Debits)
            credits = sender.ledger_entries.filter(direction="credit").aggregate(
                total=Coalesce(Sum("amount"), Value(0, output_field=DecimalField()))
            )["total"]

            debits = sender.ledger_entries.filter(direction="debit").aggregate(
                total=Coalesce(Sum("amount"), Value(0, output_field=DecimalField()))
            )["total"]

            sender_balance = credits - debits

            if sender_balance < amount and not sender.allows_overdraft:
                raise InsufficientFundsError(
                    account_id=sender.id,
                    requested_amount=amount,
                    available_balance=sender_balance,
                )

            # idempotency_key must be unique=True at the DB level — that
            # constraint is what makes the except IntegrityError block below
            # actually correct under concurrent duplicate requests.
            new_transaction = Transaction.objects.create(
                idempotency_key=idempotency_key, description=description
            )

            LedgerEntry.objects.create(
                amount=amount,
                direction="debit",
                account=sender,
                transaction=new_transaction,
            )
            LedgerEntry.objects.create(
                amount=amount,
                direction="credit",
                account=receiver,
                transaction=new_transaction,
            )

    except IntegrityError:
        # Another concurrent request won the race and already created a
        # Transaction with this idempotency_key. Return that one instead
        # of surfacing a 500 — this is what actually satisfies FR-LEDGER-4
        # under real concurrency, not just sequential retries.
        existing_transaction = Transaction.objects.filter(
            idempotency_key=idempotency_key
        ).first()
        if existing_transaction is not None:
            return existing_transaction
        raise

    return new_transaction

from django.db import transaction
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from apps.ledger.models import Account, LedgerEntry, Transaction
from common.exceptions import InsufficientFundsError, InvalidAmountError


def transfer_funds(from_account, to_account, amount, idempotency_key, description=None):

    existing_transaction = Transaction.objects.filter(
        idempotency_key=idempotency_key
    ).first()
    if existing_transaction is not None:
        return existing_transaction

    if amount <= 0:
        raise InvalidAmountError("Transaction amount must be greater than zero.")

    # Ensure we have the account IDs whether instances or UUIDs were passed
    from_id = from_account.id if isinstance(from_account, Account) else from_account
    to_id = to_account.id if isinstance(to_account, Account) else to_account

    # Sort account IDs to prevent deadlocks (consistent lock ordering requirement)
    first_id, second_id = sorted([from_id, to_id])

    with transaction.atomic():
        # Lock accounts in consistent order
        Account.objects.select_for_update(of=("self",)).get(id=first_id)
        Account.objects.select_for_update(of=("self",)).get(id=second_id)

        # Retrieve sender and receiver objects for balance checking and entries
        sender = Account.objects.get(id=from_id)
        receiver = Account.objects.get(id=to_id)

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
                "Insufficient balance unable to do transaction"
            )

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

    return new_transaction

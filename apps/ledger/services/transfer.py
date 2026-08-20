from django.db import transaction

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

    with transaction.atomic():
        sender = Account.objects.select_for_update().get(id=from_account)

        if sender.balance < amount and not sender.allows_overdraft:
            raise InsufficientFundsError(
                "Insufficient balance unable to do transaction"
            )

        new_transaction = Transaction.objects.create(
            idempotency_key=idempotency_key, description=description
        )

        LedgerEntry.objects.create(
            amount=amount,
            direction="debit",
            account_id=from_account,
            transaction_id=new_transaction.id,
        )
        LedgerEntry.objects.create(
            amount=amount,
            direction="credit",
            account_id=to_account,
            transaction_id=new_transaction.id,
        )

    return new_transaction

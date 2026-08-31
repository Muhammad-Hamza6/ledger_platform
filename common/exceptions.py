class LedgerError(Exception):
    """
    Base exception for all ledger/service-layer errors.
    Catch this in views/tests when you want to handle any ledger
    failure generically; catch the specific subclasses when you need
    to map to a specific HTTP status.
    """

    pass  # noqa: PIE790


class InsufficientFundsError(LedgerError):
    """
    Raised when a transfer would take an account below zero
    and the account does not allow overdraft.
    """

    def __init__(self, account_id, requested_amount, available_balance):
        self.account_id = account_id
        self.requested_amount = requested_amount
        self.available_balance = available_balance
        super().__init__(
            f"Insufficient funds in account {account_id}: "
            f"requested {requested_amount}, available {available_balance}."
        )


class InvalidAmountError(LedgerError):
    """
    Raised when a transfer amount is zero, negative, or otherwise
    fails business validation that the serializer didn't already catch
    (e.g. amount exceeds a configured per-transaction limit).
    """

    def __init__(self, amount):
        self.amount = amount
        super().__init__(f"Invalid transfer amount: {amount}.")


class LockTimeoutError(LedgerError):
    """
    Raised when select_for_update() cannot acquire a lock on the
    required account row(s) within the configured timeout —
    signals contention, not corruption. Callers should treat this
    as retryable (HTTP 409), not as a hard failure.
    """

    def __init__(self, account_id):
        self.account_id = account_id
        super().__init__(
            f"Could not acquire lock on account {account_id} within the timeout window."
        )


# common/exceptions.py (add this class alongside the existing ones)


class InvalidSubscriptionStateError(LedgerError):
    """
    Raised when charge_subscription() is called on a subscription that
    isn't eligible to be charged (cancelled/expired). Signals a bug in
    the caller's selection logic, not a normal business outcome.
    """

    def __init__(self, subscription_id, status):
        self.subscription_id = subscription_id
        self.status = status
        super().__init__(
            f"Cannot charge subscription {subscription_id}: "
            f"status is '{status}', expected 'active' or 'past_due'."
        )

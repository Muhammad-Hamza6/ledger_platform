# apps/subscriptions/services/charge.py

from datetime import timedelta

from django.conf import settings

from apps.ledger.models import Account
from apps.ledger.services.transfer import transfer_funds
from apps.subscriptions.models import Subscription
from common.exceptions import InsufficientFundsError, InvalidSubscriptionStateError


def get_platform_revenue_account() -> Account:
    """
    Returns the single well-known Account that receives subscription
    payments. Assumes this account has already been created once (e.g.
    via a data migration or management command) and its ID is stored in
    settings — this function does NOT create it.
    """
    return Account.objects.get(id=settings.PLATFORM_REVENUE_ACCOUNT_ID)


def _build_renewal_idempotency_key(subscription: Subscription) -> str:
    """
    Deterministic, not random — the same subscription + the same billing
    cycle (identified by the current next_renewal_at date) always produces
    the same key. This means if the renewal task runs twice for the same
    cycle (e.g. a lock TTL expiring mid-run, or a Celery retry), the second
    call safely collides with the first via transfer_funds()'s existing
    idempotency handling, instead of double-charging.
    """
    cycle_date = subscription.next_renewal_at.date().isoformat()
    return f"subscription-renewal-{subscription.id}-{cycle_date}"


def charge_subscription(subscription: Subscription) -> Subscription:
    """
    Charges a subscription for its current billing cycle and updates its
    state accordingly. This is the ONLY place that translates a
    transfer_funds() outcome into subscription status/next_renewal_at
    changes — transfer_funds() itself remains fully unaware that
    subscriptions exist.

    Returns the updated Subscription instance.

    Raises:
        InvalidSubscriptionStateError: if called on a subscription that
            isn't eligible to be charged (cancelled/expired). This is a
            programmer-error signal — the renewal task's query should
            never select such a subscription in the first place.
        LockTimeoutError, or any other non-business exception from
            transfer_funds(): propagated as-is. These are transient/infra
            issues the caller (the Celery task) should catch, log, and
            allow Celery's retry mechanism to handle — not something this
            function should swallow.
    """
    if subscription.status not in (
        Subscription.Status.ACTIVE,
        Subscription.Status.PAST_DUE,
    ):
        raise InvalidSubscriptionStateError(
            subscription_id=subscription.id,
            status=subscription.status,
        )

    platform_account = get_platform_revenue_account()
    idempotency_key = _build_renewal_idempotency_key(subscription)

    try:
        transfer_funds(
            from_account=subscription.account,
            to_account=platform_account,
            amount=subscription.plan.price,
            idempotency_key=idempotency_key,
            description=f"Subscription renewal: {subscription.plan.name}",
        )
    except InsufficientFundsError:
        # Expected, handled business outcome — not a system failure.
        # Leave next_renewal_at unchanged so the next Beat run picks this
        # subscription up again as still-due (naive retry-by-recheck for v1).
        subscription.status = Subscription.Status.PAST_DUE
        subscription.save(update_fields=["status"])
        return subscription

    # Success path
    subscription.next_renewal_at = subscription.next_renewal_at + timedelta(
        days=subscription.plan.interval_days
    )
    if subscription.status == Subscription.Status.PAST_DUE:
        subscription.status = Subscription.Status.ACTIVE
    subscription.save(update_fields=["next_renewal_at", "status"])
    return subscription

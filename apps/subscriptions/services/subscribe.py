# apps/subscriptions/services/subscribe.py

from datetime import timedelta

from django.utils import timezone

from apps.subscriptions.models import Subscription
from common.exceptions import (
    AccountOwnershipError,
    DuplicateActiveSubscriptionError,
    PlanNotActiveError,
)


def create_subscription(user, account, plan):
    """
    Creates a new active Subscription for the given user, funded by the
    given account, on the given plan. next_renewal_at is always calculated
    server-side — never accepted as client input.
    """
    if account.owner_id != user.id:
        raise AccountOwnershipError(account_id=account.id, user_id=user.id)

    if not plan.is_active:
        raise PlanNotActiveError(plan_id=plan.id)
    # apps/subscriptions/services/subscribe.py — add this check to create_subscription()

    if Subscription.objects.filter(
        user=user, account=account, plan=plan, status=Subscription.Status.ACTIVE
    ).exists():
        raise DuplicateActiveSubscriptionError(user_id=user.id, plan_id=plan.id)

    next_renewal_at = timezone.now() + timedelta(days=plan.interval_days)

    return Subscription.objects.create(
        user=user,
        account=account,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        next_renewal_at=next_renewal_at,
    )


def cancel_subscription(subscription, requesting_user):
    """
    Cancels a subscription. Idempotent: cancelling an already-cancelled
    or already-expired subscription is a no-op that returns the
    subscription unchanged, rather than raising — consistent with the
    idempotency-key philosophy used elsewhere in this project.

    Deliberately does NOT touch next_renewal_at — get_due_subscriptions()
    already excludes non-ACTIVE/PAST_DUE statuses, so a cancelled
    subscription simply stops being picked up by future renewal runs
    with no extra cleanup needed.
    """
    if subscription.user_id != requesting_user.id and requesting_user.role != "admin":
        raise AccountOwnershipError(
            account_id=subscription.account_id, user_id=requesting_user.id
        )

    if subscription.status in (
        Subscription.Status.CANCELLED,
        Subscription.Status.EXPIRED,
    ):
        return subscription

    subscription.status = Subscription.Status.CANCELLED
    subscription.cancelled_at = timezone.now()
    subscription.save(update_fields=["status", "cancelled_at"])
    return subscription

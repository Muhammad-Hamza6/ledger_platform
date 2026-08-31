# apps/subscriptions/selectors.py

from django.utils import timezone

from apps.subscriptions.models import Subscription


def get_due_subscriptions(now=None):
    """
    Returns an unpaginated, optimized queryset of subscriptions that are
    due for renewal — status is ACTIVE or PAST_DUE, and next_renewal_at
    has passed. Accepts an optional `now` override so tests can pass a
    fixed time instead of depending on real clock time.

    Purely a read — no locking, no charging happens here. That's the
    task layer's job.
    """
    now = now or timezone.now()

    return Subscription.objects.select_related("plan", "account", "user").filter(
        status__in=[Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE],
        next_renewal_at__lte=now,
    )

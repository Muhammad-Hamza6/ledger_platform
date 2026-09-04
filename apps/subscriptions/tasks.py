# apps/subscriptions/tasks.py

import logging

import redis
from celery import shared_task
from django.conf import settings
from prometheus_client import Counter

from apps.subscriptions.models import Subscription
from apps.subscriptions.selectors.subscription import get_due_subscriptions
from apps.subscriptions.services.charge import charge_subscription
from common.exceptions import InvalidSubscriptionStateError, LockTimeoutError

logger = logging.getLogger(__name__)

RENEWAL_LOCK_TTL_SECONDS = 60

_redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def charge_single_subscription(self, subscription_id):
    """
    Charges exactly ONE subscription, guarded by a Redis distributed lock
    scoped to this specific subscription. If the lock can't be acquired,
    another worker is already processing this same subscription right
    now (e.g. a duplicate Beat trigger) — this run is skipped rather than
    blocking/waiting, since it's very likely redundant.
    """
    lock_key = f"renewal_lock:{subscription_id}"
    lock = _redis_client.lock(lock_key, timeout=RENEWAL_LOCK_TTL_SECONDS)

    acquired = lock.acquire(blocking=False)
    if not acquired:
        logger.info(
            "Skipping subscription %s — already being processed (lock held).",
            subscription_id,
        )
        return

    try:
        subscription = Subscription.objects.select_related(
            "plan", "account", "user"
        ).get(id=subscription_id)

        try:
            charge_subscription(subscription)
            logger.info(
                "Successfully processed renewal for subscription %s", subscription_id
            )
        except InvalidSubscriptionStateError as exc:
            # Programmer-error signal — the selector should never have
            # picked this one up. Log loudly, don't retry.
            logger.error(
                "Subscription %s was not eligible for charging: %s",
                subscription_id,
                exc,
            )
        except LockTimeoutError as exc:
            # Transient infra issue from transfer_funds()'s own account
            # locking — genuinely retryable.
            logger.warning(
                "Lock timeout charging subscription %s, retrying: %s",
                subscription_id,
                exc,
            )
            raise self.retry(exc=exc)

    finally:
        # Only release if we still hold it — avoids releasing a lock that
        # expired and was re-acquired by someone else in an edge case.
        try:
            lock.release()
        except redis.exceptions.LockError:
            pass


@shared_task
def process_subscription_renewals():
    """
    Scheduled entry point (triggered daily by Celery Beat). Finds all
    subscriptions due for renewal and fans out one charge_single_subscription
    task per subscription, rather than charging inline in a loop — so a
    failure on one subscription never affects the others, and each charge
    gets its own retry/task history.
    """
    due_subscriptions = get_due_subscriptions()
    count = due_subscriptions.count()
    logger.info("Found %d subscriptions due for renewal.", count)

    for subscription in due_subscriptions:
        charge_single_subscription.delay(subscription.id)

    return count


renewal_charge_outcomes = Counter(
    "subscription_renewal_charge_total",
    "Count of subscription renewal charge attempts by outcome",
    ["outcome"],  # "success", "past_due", "invalid_state"
)

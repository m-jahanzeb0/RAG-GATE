"""
Celery tasks for RAG-Gate.

These tasks run asynchronously in the Celery worker and are used for
non-blocking operations: DB quota persistence, request logging, analytics, etc.

The quota enforcement itself happens inline via Redis atomic INCR —
these tasks are purely for record-keeping and analytics.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def update_db_quota(user_id: int) -> None:
    """
    Persist the current quota usage to the database.

    This is called asynchronously after each successful LLM response.
    The real-time enforcement happens in Redis; this task keeps the
    DB model in sync for historical queries and the quota check endpoint.

    Args:
        user_id: The Django user ID whose quota should be updated.
    """
    try:
        from django.contrib.auth import get_user_model
        from gateway.models import APIQuota

        User = get_user_model()

        user = User.objects.get(pk=user_id)
        quota, created = APIQuota.objects.get_or_create(
            user=user,
            defaults={"daily_limit": 30},
        )
        quota.increment_usage()

        logger.debug(
            "Updated DB quota for user %d: %d/%d used",
            user_id,
            quota.requests_used,
            quota.daily_limit,
        )
    except Exception as e:
        logger.error("Failed to update DB quota for user %d: %s", user_id, e)


@shared_task(ignore_result=True)
def reset_all_quotas() -> None:
    """
    Reset all daily quota counters.

    Scheduled via Celery Beat at midnight UTC.
    This is a safety net — the automatic reset_if_needed() logic on
    each request should handle most cases, but this ensures consistency.
    """
    try:
        from gateway.models import APIQuota
        from django.utils import timezone

        now = timezone.now()
        updated = APIQuota.objects.all().update(
            requests_used=0,
            last_reset=now,
        )
        logger.info("Reset quotas for %d users at %s", updated, now)
    except Exception as e:
        logger.error("Failed to reset quotas: %s", e)


@shared_task(ignore_result=True)
def log_request(user_id: int, provider: str, model: str, status: str) -> None:
    """
    Log an LLM API request for analytics and auditing.

    Persists a RequestLog record in the database. These records are
    aggregated by the GET /api/v1/analytics/ endpoint to power the
    dashboard metrics.

    Args:
        user_id: The Django user ID.
        provider: The LLM provider name.
        model: The model identifier.
        status: "success" or "error".
    """
    try:
        from django.contrib.auth import get_user_model
        from gateway.models import RequestLog

        User = get_user_model()
        user = User.objects.get(pk=user_id)

        RequestLog.objects.create(
            user=user,
            provider=provider,
            model=model,
            status=status,
        )

        logger.info(
            "Logged request — user=%d provider=%s model=%s status=%s",
            user_id, provider, model, status,
        )
    except Exception as e:
        logger.error("Failed to log request for user %d: %s", user_id, e)
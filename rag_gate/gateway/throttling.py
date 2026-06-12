"""
Redis-backed atomic quota enforcement for RAG-Gate.

This throttling class performs an atomic INCR against Redis BEFORE the
LLM request is proxied. This prevents race conditions where concurrent
requests could all pass the quota check before any of them decrements.

Architecture:
    - Key: quota:{user_id}:{YYYY-MM-DD}
    - TTL: Set to seconds until midnight on first INCR
    - Atomic: redis INCR returns the new value atomically
    - If INCR result > daily_limit, return 429 immediately
    - The DB model (APIQuota) is updated async via Celery for persistence
"""

from datetime import datetime, timezone as dt_timezone
import logging

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
import redis as redis_module

logger = logging.getLogger(__name__)


class RedisQuotaThrottle:
    """
    DRF-compatible throttle that enforces daily request limits via Redis atomic counters.

    This runs inline (synchronously) before any LLM call to prevent quota bypass
    under concurrent load.
    """

    def __init__(self):
        self.redis_client = None
        self.cache = cache  # Django cache framework (configured for Redis)

    def _get_redis(self):
        """Lazy-init Redis client from Django cache backend."""
        if self.redis_client is None:
            # Use the redis library directly for atomic INCR with EXPIRE
            try:
                self.redis_client = redis_module.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                )
                self.redis_client.ping()
            except redis_module.ConnectionError as e:
                logger.warning("Redis unavailable, falling back to DB-only quota: %s", e)
                self.redis_client = None
        return self.redis_client

    def _quota_key(self, user_id: int) -> str:
        """Generate the Redis key for a user's daily quota."""
        today = timezone.now().strftime("%Y-%m-%d")
        return f"quota:{user_id}:{today}"

    def _seconds_until_midnight(self) -> int:
        """Calculate seconds remaining until midnight UTC."""
        now = datetime.now(dt_timezone.utc)
        midnight = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        # Add 1 second to roll into the next day
        seconds = int((midnight - now).total_seconds()) + 1
        return max(1, seconds)

    def allow_request(self, user_id: int) -> tuple[bool, int]:
        """
        Check if the user has quota remaining.

        Returns:
            (allowed: bool, remaining: int)
        """
        r = self._get_redis()
        if r is None:
            # Redis unavailable — allow request but log warning
            # The DB model will catch overuse on the next Celery sync
            logger.warning("Redis unavailable for quota check — allowing request by default")
            return True, settings.QUOTA_DAILY_LIMIT

        key = self._quota_key(user_id)
        daily_limit = settings.QUOTA_DAILY_LIMIT

        try:
            # Atomic INCR — guarantees no race conditions
            current_count = r.incr(key)

            if current_count == 1:
                # First request today — set TTL until midnight
                ttl = self._seconds_until_midnight()
                r.expire(key, ttl)

            remaining = max(0, daily_limit - current_count)

            if current_count > daily_limit:
                logger.info(
                    "Quota exceeded for user %d: %d/%d used",
                    user_id, current_count, daily_limit,
                )
                return False, remaining

            return True, remaining

        except redis_module.RedisError as e:
            logger.error("Redis error during quota check: %s", e)
            return True, daily_limit  # Fail open — allow request

    def get_remaining(self, user_id: int) -> int:
        """Get the remaining quota without incrementing."""
        r = self._get_redis()
        if r is None:
            return settings.QUOTA_DAILY_LIMIT

        key = self._quota_key(user_id)
        try:
            current = int(r.get(key) or 0)
            return max(0, settings.QUOTA_DAILY_LIMIT - current)
        except (redis_module.RedisError, ValueError, TypeError):
            return settings.QUOTA_DAILY_LIMIT
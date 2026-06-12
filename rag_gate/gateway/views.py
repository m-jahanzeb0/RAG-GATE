"""
DRF views for RAG-Gate API Gateway.

Implements:
  - POST /api/v1/chat/ — Dual-mode unary/streaming LLM proxy
  - GET /api/v1/quota/ — Check remaining quota
  - GET /api/v1/analytics/ — Aggregated request analytics

The quota check is performed INLINE via Redis atomic INCR before any
LLM request is proxied. This prevents concurrent request bypass.

Streaming uses Django StreamingHttpResponse with Server-Sent Events format.
"""

import json
import logging

from django.conf import settings
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework.views import exception_handler

from gateway.authentication import APIKeyAuthentication
from gateway.models import APIQuota, RequestLog
from gateway.serializers import ChatRequestSerializer
from gateway.throttling import RedisQuotaThrottle
from llm.registry import ProviderRegistry
from llm.tasks import update_db_quota as _update_db_quota
from llm.tasks import log_request as _log_request

logger = logging.getLogger(__name__)

# Instantiate throttle and registry once (they hold no per-request state)
quota_throttle = RedisQuotaThrottle()
provider_registry = ProviderRegistry()


def custom_exception_handler(exc, context):
    """
    Custom DRF exception handler that formats 429 responses with quota info.
    """
    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(exc, Throttled):
            request = context.get("request")
            remaining = 0
            if request and request.user.is_authenticated:
                remaining = quota_throttle.get_remaining(request.user.pk)
            response.data = {
                "error": "Daily quota exceeded",
                "detail": str(exc),
                "quota_remaining": remaining,
                "quota_limit": settings.QUOTA_DAILY_LIMIT,
            }
    return response


def _authenticate(request):
    """Helper to authenticate and return (user, error_response)."""
    auth = APIKeyAuthentication()
    auth_result = auth.authenticate(request)
    if auth_result is None:
        return None, Response(
            {"detail": "Authentication credentials were not provided."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    return auth_result[0], None


@api_view(["POST"])
def chat_completion(request):
    """
    Proxy a chat completion request to the specified LLM provider.

    Supports both unary and streaming modes via the `stream` parameter.
    """
    user, error = _authenticate(request)
    if error:
        return error

    serializer = ChatRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data

    # === ATOMIC QUOTA CHECK (INLINE, BEFORE LLM CALL) ===
    allowed, remaining = quota_throttle.allow_request(user.pk)
    if not allowed:
        raise Throttled(
            detail=f"Daily quota of {settings.QUOTA_DAILY_LIMIT} requests exceeded"
        )

    # Resolve the LLM provider service
    try:
        provider = provider_registry.get_provider(
            provider_name=data["provider"],
            model=data["model"],
            base_url=data.get("base_url") or None,
            api_key_override=data.get("api_key_override") or None,
        )
    except ValueError as e:
        return Response(
            {"error": str(e), "provider": data["provider"]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    llm_kwargs = {
        "messages": data["messages"],
        "max_tokens": data["max_tokens"],
        "temperature": data["temperature"],
    }

    if data["stream"]:
        return _handle_streaming_response(
            provider, data["model"], data["provider"], llm_kwargs, remaining, user
        )
    else:
        return _handle_unary_response(
            provider, data["model"], data["provider"], llm_kwargs, remaining, user
        )


def _handle_unary_response(provider, model, provider_name, kwargs, quota_remaining, user):
    """Unary mode: collect all tokens, return a standard JSON response."""
    try:
        collected_content = ""
        usage = {"prompt_tokens": 0, "completion_tokens": 0}

        for chunk in provider.generate_response(model=model, **kwargs):
            if isinstance(chunk, dict):
                usage = chunk.get("usage", usage)
            elif isinstance(chunk, str):
                collected_content += chunk

        _update_db_quota.delay(user.pk)
        _log_request.delay(user.pk, provider_name, model, "success")

        return Response({
            "id": f"chatcmpl-{timezone.now().timestamp():.0f}",
            "model": model,
            "provider": provider_name,
            "content": collected_content,
            "usage": usage,
            "quota_remaining": quota_remaining - 1 if quota_remaining > 0 else 0,
        })

    except Exception as e:
        logger.exception("LLM provider error for %s: %s", provider_name, e)
        _log_request.delay(user.pk, provider_name, model, "error")
        return Response(
            {"error": f"Provider error: {str(e)}", "provider": provider_name},
            status=status.HTTP_502_BAD_GATEWAY,
        )


def _handle_streaming_response(provider, model, provider_name, kwargs, quota_remaining, user):
    """Streaming mode: stream tokens back as Server-Sent Events."""
    def event_stream():
        try:
            for chunk in provider.generate_response(model=model, **kwargs):
                if isinstance(chunk, dict):
                    yield f"data: {json.dumps({'event': 'done', 'usage': chunk.get('usage', {}), 'quota_remaining': max(0, quota_remaining - 1)})}\n\n"
                    break
                elif isinstance(chunk, str):
                    yield f"data: {json.dumps({'event': 'token', 'token': chunk, 'model': model})}\n\n"

            _update_db_quota.delay(user.pk)
            _log_request.delay(user.pk, provider_name, model, "success")
        except Exception as e:
            logger.exception("Streaming error for %s: %s", provider_name, e)
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@api_view(["GET"])
def quota_check(request):
    """
    Return the user's remaining daily quota.
    """
    user, error = _authenticate(request)
    if error:
        return error

    redis_remaining = quota_throttle.get_remaining(user.pk)
    db_quota, created = APIQuota.objects.get_or_create(
        user=user,
        defaults={"daily_limit": settings.QUOTA_DAILY_LIMIT},
    )
    db_quota.reset_if_needed()

    remaining = min(redis_remaining, db_quota.remaining)

    return Response({
        "daily_limit": settings.QUOTA_DAILY_LIMIT,
        "requests_used": settings.QUOTA_DAILY_LIMIT - remaining,
        "remaining": remaining,
        "reset_date": db_quota.last_reset,
    })


@api_view(["GET"])
def analytics(request):
    """
    Return aggregated request analytics for the authenticated user.

    Provides:
      - Total requests in the last 30 days
      - Current day usage
      - Quota limit
      - Breakdown by provider
      - Daily usage history for the last 7 days
    """
    user, error = _authenticate(request)
    if error:
        return error

    now = timezone.now()
    thirty_days_ago = now - timezone.timedelta(days=30)
    seven_days_ago = now - timezone.timedelta(days=7)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Total requests in last 30 days
    total_requests_30_days = RequestLog.objects.filter(
        user=user, created_at__gte=thirty_days_ago
    ).count()

    # Current day usage
    current_day_usage = RequestLog.objects.filter(
        user=user, created_at__gte=today_start
    ).count()

    # Provider distribution (last 30 days)
    provider_counts = (
        RequestLog.objects
        .filter(user=user, created_at__gte=thirty_days_ago)
        .values("provider")
        .annotate(count=Count("id"))
    )
    provider_distribution = {item["provider"]: item["count"] for item in provider_counts}

    # Daily usage history for last 7 days
    daily_counts = (
        RequestLog.objects
        .filter(user=user, created_at__gte=seven_days_ago)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    usage_history_7_days = [
        {"date": item["date"].isoformat(), "count": item["count"]}
        for item in daily_counts
    ]

    # Get quota limit from DB or settings
    try:
        db_quota = APIQuota.objects.get(user=user)
        quota_limit = db_quota.daily_limit
    except APIQuota.DoesNotExist:
        quota_limit = settings.QUOTA_DAILY_LIMIT

    return Response({
        "total_requests_30_days": total_requests_30_days,
        "current_day_usage": current_day_usage,
        "quota_limit": quota_limit,
        "provider_distribution": provider_distribution,
        "usage_history_7_days": usage_history_7_days,
    })
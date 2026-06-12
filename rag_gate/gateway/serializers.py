from rest_framework import serializers

from .models import APIKey


class QuotaCheckSerializer(serializers.Serializer):
    """Response serializer for quota check endpoint."""

    daily_limit = serializers.IntegerField()
    requests_used = serializers.IntegerField()
    remaining = serializers.IntegerField()
    reset_date = serializers.DateTimeField()


class ChatRequestSerializer(serializers.Serializer):
    """Validates incoming chat/completion requests."""

    provider = serializers.ChoiceField(
        choices=["openai", "anthropic", "openai-compatible"],
        required=True,
    )
    model = serializers.CharField(required=True, max_length=256)
    messages = serializers.ListField(
        child=serializers.DictField(),
        required=True,
        min_length=1,
    )
    stream = serializers.BooleanField(default=False)
    max_tokens = serializers.IntegerField(default=1024, min_value=1, max_value=128000)
    temperature = serializers.FloatField(default=0.7, min_value=0.0, max_value=2.0)
    base_url = serializers.URLField(required=False, allow_blank=True)
    api_key_override = serializers.CharField(required=False, allow_blank=True)

    def validate_messages(self, value):
        """Ensure each message has the required fields."""
        for i, msg in enumerate(value):
            if "role" not in msg or "content" not in msg:
                raise serializers.ValidationError(
                    f"Message at index {i} must contain 'role' and 'content' keys"
                )
            if msg["role"] not in ("system", "user", "assistant"):
                raise serializers.ValidationError(
                    f"Invalid role '{msg['role']}' at index {i}. Must be system, user, or assistant"
                )
        return value


class AnalyticsSerializer(serializers.Serializer):
    """Response serializer for the analytics endpoint."""

    total_requests_30_days = serializers.IntegerField()
    current_day_usage = serializers.IntegerField()
    quota_limit = serializers.IntegerField()
    provider_distribution = serializers.DictField(
        child=serializers.IntegerField()
    )
    usage_history_7_days = serializers.ListField(
        child=serializers.DictField()
    )


class APIKeySerializer(serializers.ModelSerializer):
    """Serializer for API Key CRUD operations."""

    class Meta:
        model = APIKey
        fields = ["id", "name", "key", "is_active", "created_at"]
        read_only_fields = ["id", "key", "created_at"]
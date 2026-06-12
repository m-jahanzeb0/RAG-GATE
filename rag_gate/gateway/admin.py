from django.contrib import admin

from .models import APIKey, APIQuota, RequestLog


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "key_prefix", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "user__username", "key")

    @admin.display(description="Key Prefix")
    def key_prefix(self, obj):
        return obj.key[:12] + "..."


@admin.register(APIQuota)
class APIQuotaAdmin(admin.ModelAdmin):
    list_display = ("user", "daily_limit", "requests_used", "remaining", "last_reset")
    list_filter = ("last_reset",)
    search_fields = ("user__username",)


@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "model", "status", "created_at")
    list_filter = ("provider", "status", "created_at")
    search_fields = ("user__username", "provider", "model")
    date_hierarchy = "created_at"
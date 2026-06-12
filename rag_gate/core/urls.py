"""
Root URL configuration for RAG-Gate.

Strictly no views imported here. All routing is delegated to the gateway app.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("gateway.urls")),
]
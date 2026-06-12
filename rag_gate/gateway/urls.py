from django.urls import path

from . import views

app_name = "gateway"

urlpatterns = [
    path("chat/", views.chat_completion, name="chat-completion"),
    path("quota/", views.quota_check, name="quota-check"),
    path("analytics/", views.analytics, name="analytics"),
]

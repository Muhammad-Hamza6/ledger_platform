# apps/subscriptions/urls.py

from django.urls import path

from apps.subscriptions.views import (
    SubscriptionCancelView,
    SubscriptionCreateView,
    SubscriptionListView,
)

app_name = "subscriptions"

urlpatterns = [
    path(
        "subscriptions/", SubscriptionCreateView.as_view(), name="subscription-create"
    ),
    path(
        "subscriptions/list/", SubscriptionListView.as_view(), name="subscription-list"
    ),
    path(
        "subscriptions/<uuid:subscription_id>/",
        SubscriptionCancelView.as_view(),
        name="subscription-cancel",
    ),
]

from debug_toolbar.toolbar import debug_toolbar_urls
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.users.urls")),
    path("api/v1/", include("apps.ledger.urls", namespace="ledger")),
    path("api/v1/", include("apps.subscriptions.urls", namespace="subscriptions")),
] + debug_toolbar_urls()

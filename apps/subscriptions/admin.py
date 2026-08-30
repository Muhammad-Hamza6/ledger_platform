from django.contrib import admin

from .models import Subscription, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ["name", "price", "currency", "interval_days", "is_active"]  # noqa: RUF012
    list_filter = ["is_active", "interval_days"]  # noqa: RUF012


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "plan", "status", "next_renewal_at"]  # noqa: RUF012
    list_filter = ["status"]  # noqa: RUF012
    readonly_fields = ["started_at"]  # noqa: RUF012

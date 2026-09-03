from django.contrib import admin

from apps.ledger.models import BalanceDiscrepancy


@admin.register(BalanceDiscrepancy)
class BalanceDiscrepancyAdmin(admin.ModelAdmin):
    list_display = [  # noqa: RUF012
        "account",
        "discrepancy_amount",
        "detected_at",
        "resolved_at",
    ]
    list_filter = ["resolved_at"]  # noqa: RUF012
    readonly_fields = [  # noqa: RUF012
        "account",
        "cached_balance_at_check",
        "derived_balance_at_check",
        "discrepancy_amount",
        "detected_at",
    ]

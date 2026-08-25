# apps/ledger/urls.py

from django.urls import path

from apps.ledger.views import (
    AccountBalanceView,
    AccountCreateView,
    AccountTransactionHistoryView,
    TransferCreateView,
)

app_name = "ledger"

urlpatterns = [
    path("accounts/", AccountCreateView.as_view(), name="account-create"),
    path(
        "accounts/<uuid:account_id>/balance/",
        AccountBalanceView.as_view(),
        name="account-balance",
    ),
    path(
        "accounts/<uuid:account_id>/transactions/",
        AccountTransactionHistoryView.as_view(),
        name="account-transactions",
    ),
    path("transactions/", TransferCreateView.as_view(), name="transfer-create"),
]

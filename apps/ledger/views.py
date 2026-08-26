# apps/ledger/views.py

from rest_framework import permissions, status
from rest_framework.generics import CreateAPIView, ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.ledger.models import Account
from apps.ledger.selectors.account import get_account_balance, get_account_transactions
from apps.ledger.serializers import (
    AccountBalanceSerializer,
    AccountSerializer,
    LedgerEntrySerializer,
    TransferSerializer,
)
from apps.ledger.services.transfer import transfer_funds
from common.exceptions import (
    InsufficientFundsError,
    InvalidAmountError,
    LockTimeoutError,
)


class IsAccountOwner(permissions.BasePermission):
    """
    Object-level permission — only the account's owner (or an admin)
    may view or act on it.
    """

    def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.id or request.user.role == "admin"


class AccountCreateView(CreateAPIView):
    """
    POST /api/v1/accounts/
    Owner is always the requesting user — never trust a client-supplied owner field.
    """

    serializer_class = AccountSerializer
    permission_classes = [permissions.IsAuthenticated]  # noqa: RUF012

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class AccountBalanceView(RetrieveAPIView):
    """
    GET /api/v1/accounts/{id}/balance/
    Delegates entirely to the selector — this view has no business logic,
    just permission checks and response shaping.
    """

    permission_classes = [permissions.IsAuthenticated, IsAccountOwner]  # noqa: RUF012
    lookup_url_kwarg = "account_id"

    def get_queryset(self):
        return Account.objects.filter(is_active=True)

    def retrieve(self, request, *args, **kwargs):
        account = self.get_object()  # runs has_object_permission via DRF
        balance = get_account_balance(account)
        data = {
            "account_id": account.id,
            "balance": balance,
            "currency": account.currency,
        }
        serializer = AccountBalanceSerializer(data)
        return Response(serializer.data)


class AccountTransactionHistoryView(ListAPIView):
    """
    GET /api/v1/accounts/{id}/transactions/
    Paginated, delegates to the selector for the actual query.
    """

    serializer_class = LedgerEntrySerializer
    permission_classes = [permissions.IsAuthenticated, IsAccountOwner]  # noqa: RUF012
    lookup_url_kwarg = "account_id"

    def get_queryset(self):
        account = self._get_account()
        return get_account_transactions(account)

    def _get_account(self):
        account = Account.objects.get(id=self.kwargs["account_id"])
        self.check_object_permissions(self.request, account)
        return account


class TransferRateThrottle(UserRateThrottle):
    scope = "transfer"


class TransferCreateView(APIView):
    """
    POST /api/v1/transactions/
    The ONLY place transfer_funds() is called from the HTTP layer.
    Serializer validates shape; this view maps service-layer exceptions
    to the right HTTP status codes — that mapping is a deliberate
    design decision, not an afterthought.
    """

    permission_classes = [permissions.IsAuthenticated]  # noqa: RUF012
    throttle_classes = [TransferRateThrottle]  # noqa: RUF012

    def post(self, request, *args, **kwargs):
        from_account = self._resolve_from_account(request)

        serializer = TransferSerializer(
            data=request.data,
            context={"from_account": from_account, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        try:
            transaction = transfer_funds(
                from_account=from_account,
                to_account=serializer.validated_data["to_account"],
                amount=serializer.validated_data["amount"],
                idempotency_key=serializer.validated_data["idempotency_key"],
                description=serializer.validated_data.get("description", ""),
            )
        except InsufficientFundsError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        except InvalidAmountError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except LockTimeoutError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(
            {"transaction_id": transaction.id, "status": transaction.status},
            status=status.HTTP_201_CREATED,
        )

    def _resolve_from_account(self, request):
        """
        The source account is derived from the authenticated user,
        never accepted as client input. Currently assumes one primary
        account per user — adjust if you support multiple accounts
        with an explicit account selector instead.
        """
        account = Account.objects.filter(owner=request.user, is_active=True).first()
        if account is None:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("No active account found for this user.")
        return account

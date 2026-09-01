# apps/subscriptions/views.py

from rest_framework import permissions, status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.subscriptions.models import Subscription
from apps.subscriptions.serializers import (
    SubscriptionCreateSerializer,
    SubscriptionSerializer,
)
from apps.subscriptions.services import cancel_subscription, create_subscription
from common.exceptions import AccountOwnershipError, PlanNotActiveError


class IsSubscriptionOwner(permissions.BasePermission):
    """
    Object-level permission — only the subscription's own user (or an
    admin) may view/cancel it. Structurally identical to IsAccountOwner,
    just pointed at Subscription.user instead of Account.owner.
    """

    def has_object_permission(self, request, view, obj):
        return obj.user_id == request.user.id or request.user.role == "admin"


class SubscriptionCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]  # noqa: RUF012

    def post(self, request, *args, **kwargs):
        serializer = SubscriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            subscription = create_subscription(
                user=request.user,
                account=serializer.validated_data["account"],
                plan=serializer.validated_data["plan"],
            )
        except AccountOwnershipError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except PlanNotActiveError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        return Response(
            SubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED
        )


class SubscriptionListView(ListAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]  # noqa: RUF012

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user).select_related(
            "plan", "account"
        )


class SubscriptionCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSubscriptionOwner]  # noqa: RUF012

    def delete(self, request, *args, **kwargs):
        subscription = self._get_subscription()

        try:
            updated = cancel_subscription(
                subscription=subscription, requesting_user=request.user
            )
        except AccountOwnershipError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        return Response(SubscriptionSerializer(updated).data, status=status.HTTP_200_OK)

    def _get_subscription(self):
        subscription = Subscription.objects.select_related("plan", "account").get(
            id=self.kwargs["subscription_id"]
        )
        self.check_object_permissions(self.request, subscription)
        return subscription

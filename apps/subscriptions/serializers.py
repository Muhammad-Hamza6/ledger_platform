# apps/subscriptions/serializers.py

from rest_framework import serializers

from apps.ledger.models import Account
from apps.subscriptions.models import Subscription, SubscriptionPlan


class SubscriptionCreateSerializer(serializers.Serializer):
    """
    Validates SHAPE only — no side effects, no create() method. The view
    calls create_subscription() after this passes, same discipline as
    TransferSerializer.
    """

    plan = serializers.PrimaryKeyRelatedField(
        queryset=SubscriptionPlan.objects.filter(is_active=True)
    )
    account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.filter(is_active=True)
    )


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    plan_price = serializers.DecimalField(
        source="plan.price", max_digits=19, decimal_places=4, read_only=True
    )

    class Meta:
        model = Subscription
        fields = [  # noqa: RUF012
            "id",
            "plan",
            "plan_name",
            "plan_price",
            "account",
            "status",
            "next_renewal_at",
            "started_at",
            "cancelled_at",
        ]
        read_only_fields = fields

# apps/ledger/serializers.py

from decimal import Decimal

from rest_framework import serializers

from apps.ledger.models import Account, LedgerEntry


class AccountSerializer(serializers.ModelSerializer):
    """
    Handles account creation and read representation.
    No business logic here — 'owner' is set from request.user in the view,
    not derived or guessed here.
    """

    class Meta:
        model = Account
        fields = [  # noqa: RUF012
            "id",
            "name",
            "currency",
            "allows_overdraft",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "is_active", "created_at"]  # noqa: RUF012

    def validate_currency(self, value):
        if len(value) != 3 or not value.isalpha():
            raise serializers.ValidationError(
                "Currency must be a 3-letter ISO 4217 code, e.g. 'USD'."
            )
        return value.upper()


class AccountBalanceSerializer(serializers.Serializer):
    """
    Output-only serializer for the balance selector result.
    Not a ModelSerializer — balance isn't a model field, it's derived.
    """

    account_id = serializers.UUIDField()
    balance = serializers.DecimalField(max_digits=19, decimal_places=4)
    currency = serializers.CharField()


class LedgerEntrySerializer(serializers.ModelSerializer):
    """
    Read-only representation of a single ledger entry,
    used inside transaction history responses.
    """

    class Meta:
        model = LedgerEntry
        fields = [  # noqa: RUF012
            "id",
            "transaction",
            "account",
            "amount",
            "direction",
            "created_at",
        ]
        read_only_fields = fields


class TransferSerializer(serializers.Serializer):
    """
    Validates the SHAPE of a transfer request only.
    Does NOT call transfer_funds() itself — the view is responsible for
    invoking the service layer after this serializer confirms the input
    is well-formed. Keeping that boundary is the whole point of this story.
    """

    to_account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.filter(is_active=True)
    )
    amount = serializers.DecimalField(max_digits=19, decimal_places=4)
    idempotency_key = serializers.CharField(max_length=255)
    description = serializers.CharField(
        max_length=500, required=False, allow_blank=True
    )

    def validate_amount(self, value):
        if value <= Decimal("0"):  # noqa: FURB157
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate(self, attrs):
        # from_account comes from context (request.user's account), not client input —
        # never trust the client to tell you which account they're sending FROM.
        from_account = self.context.get("from_account")
        to_account = attrs["to_account"]

        if from_account is None:
            raise serializers.ValidationError("Source account context is required.")

        if from_account.id == to_account.id:
            raise serializers.ValidationError("Cannot transfer to the same account.")

        return attrs

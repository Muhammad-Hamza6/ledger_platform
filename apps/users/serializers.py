from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [  # noqa: RUF012
            "id",
            "email",
            "date_joined",
        ]  # Exclude password, is_staff, etc.


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ["email", "password", "password_confirm"]  # noqa: RUF012

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Password fields didn't match."}
            )
        return attrs

    def create(self, validated_data):
        # Remove password_confirm before creating user
        validated_data.pop("password_confirm")

        # Use create_user so Django securely hashes the password
        user = User.objects.create_user(
            email=validated_data["email"], password=validated_data["password"]
        )
        return user

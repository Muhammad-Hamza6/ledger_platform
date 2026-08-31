import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.ledger.models import Account
from apps.users.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def create_user(django_user_model):
    def _create_user(email="user@example.com", password="testpass123", **kwargs):
        return django_user_model.objects.create_user(
            email=email, password=password, **kwargs
        )

    return _create_user


@pytest.fixture
def authenticated_client(api_client, create_user):
    user = create_user()
    response = api_client.post(
        "/api/v1/auth/token/",
        {"email": user.email, "password": "testpass123"},
    )
    token = response.data["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client, user


@pytest.fixture
def platform_revenue_account(django_user_model):
    system_user, _ = User.objects.get_or_create(
        email="platform-system@internal.ledgerplatform",
        defaults={"is_active": True},
    )
    account, _ = Account.objects.get_or_create(
        id=settings.PLATFORM_REVENUE_ACCOUNT_ID,
        defaults={
            "owner": system_user,
            "name": "platform_revenue",
            "currency": "USD",
        },
    )
    return account

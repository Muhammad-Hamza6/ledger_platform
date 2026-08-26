import pytest
from rest_framework.test import APIClient


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

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class JWTAuthenticationGuardTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="auth_test@example.com", password="StrongPassword123!"
        )
        self.protected_url = reverse("auth-protected-test")

    def test_expired_or_invalid_token_returns_401(self):
        """Guarantees that broken or fake tokens return an explicit 401 Unauthorized."""
        self.client.credentials(
            HTTP_AUTHORIZATION="Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fakeinvalidtoken"
        )
        response = self.client.get(self.protected_url)
        # Strict assertion verifying it hits 401 instead of crashing with 500
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_token_returns_401(self):
        """Guarantees requests without headers fail cleanly with 401."""
        response = self.client.get(self.protected_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

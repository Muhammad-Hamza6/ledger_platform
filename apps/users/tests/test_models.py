from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.test import TestCase

User = get_user_model()


class UserModelTest(TestCase):
    def test_create_user(self):
        """Test that a user can be created successfully with an email."""
        user = User.objects.create_user(
            email="test@example.com", password="securepassword123"
        )
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("securepassword123"))
        self.assertFalse(user.is_staff)
        self.assertTrue(user.is_active)

    def test_email_uniqueness(self):
        """Test that creating two users with the same email raises an IntegrityError."""
        User.objects.create_user(email="duplicate@example.com", password="password123")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email="duplicate@example.com", password="password456"
            )

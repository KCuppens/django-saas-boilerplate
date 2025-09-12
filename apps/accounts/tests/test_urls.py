"""Test URL routing for accounts app."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class TestAccountsUrls(TestCase):
    """Test URL patterns for accounts app."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

    def test_profile_update_url(self):
        """Test profile update URL resolves correctly."""
        url = reverse("api-profile-update")
        self.assertEqual(url, "/accounts/profile/update/")

    def test_password_reset_request_url(self):
        """Test password reset request URL resolves correctly."""
        url = reverse("api-password-reset")
        self.assertEqual(url, "/accounts/password-reset/")

    def test_password_reset_confirm_url(self):
        """Test password reset confirm URL resolves correctly."""
        url = reverse("api-password-reset-confirm")
        self.assertEqual(url, "/accounts/password-reset/confirm/")

    def test_email_verification_url(self):
        """Test email verification URL resolves correctly."""
        url = reverse("api-verify-email")
        self.assertEqual(url, "/accounts/verify-email/")

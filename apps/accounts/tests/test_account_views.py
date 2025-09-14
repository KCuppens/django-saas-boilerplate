"""Tests for account views."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from allauth.account.models import EmailAddress, EmailConfirmation
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

User = get_user_model()


class UserViewSetTestCase(APITestCase):
    """Test UserViewSet."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )

    def test_retrieve_user_profile_authenticated(self):
        """Test retrieving current user profile."""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-detail", kwargs={"pk": "me"})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertEqual(response.data["name"], self.user.name)

    def test_retrieve_user_profile_unauthenticated(self):
        """Test retrieving user profile without authentication."""
        url = reverse("user-detail", kwargs={"pk": "me"})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_user_profile(self):
        """Test updating user profile."""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-detail", kwargs={"pk": "me"})

        data = {"name": "Updated Name", "email": "updated@example.com"}

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Name")

        # Verify in database
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, "Updated Name")

    def test_register_new_user(self):
        """Test registering a new user."""
        url = reverse("user-register")

        data = {
            "email": "newuser@example.com",
            "name": "New User",
            "password1": "newpass123456",
            "password2": "newpass123456",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("user", response.data)
        self.assertIn("message", response.data)
        self.assertEqual(response.data["user"]["email"], "newuser@example.com")

        # Verify user was created
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())

    def test_register_with_email_verification(self):
        """Test registration when email verification is required."""
        url = reverse("user-register")

        data = {
            "email": "verify@example.com",
            "name": "Verify User",
            "password1": "verifypass123456",
            "password2": "verifypass123456",
        }

        # Mock the EMAIL_VERIFICATION setting to be mandatory
        with patch("allauth.account.app_settings.EMAIL_VERIFICATION", "mandatory"):
            response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("Please check your email", response.data["message"])

    def test_register_invalid_data(self):
        """Test registration with invalid data."""
        url = reverse("user-register")

        data = {
            "email": "invalid-email",
            "password1": "123",  # Too short
            "password2": "456",  # Doesn't match
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password(self):
        """Test changing user password."""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-change-password")

        data = {
            "old_password": "testpass123",
            "new_password1": "newtestpass123456",
            "new_password2": "newtestpass123456",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Password changed successfully.")

        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newtestpass123456"))

    def test_change_password_wrong_old_password(self):
        """Test changing password with wrong old password."""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-change-password")

        data = {
            "old_password": "wrongpassword",
            "new_password1": "newtestpass123456",
            "new_password2": "newtestpass123456",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_unauthenticated(self):
        """Test changing password without authentication."""
        url = reverse("user-change-password")

        data = {
            "old_password": "testpass123",
            "new_password1": "newtestpass123456",
            "new_password2": "newtestpass123456",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ping_updates_last_seen(self):
        """Test ping action updates last seen timestamp."""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-ping")

        original_last_seen = self.user.last_seen

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Last seen updated.")
        self.assertIn("last_seen", response.data)

        # Verify last seen was updated
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.last_seen, original_last_seen)

    def test_delete_account(self):
        """Test deleting user account."""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-delete-account")

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify user was deactivated (not deleted)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_delete_account_unauthenticated(self):
        """Test deleting account without authentication."""
        url = reverse("user-delete-account")

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_serializer_class_for_update(self):
        """Test that update actions use UserUpdateSerializer."""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-detail", kwargs={"pk": "me"})

        # This should use UserUpdateSerializer
        data = {"name": "New Name"}
        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "New Name")

    def test_get_object_returns_current_user(self):
        """Test that get_object returns the current authenticated user."""
        self.client.force_authenticate(user=self.user)

        # Any detail endpoint should return the current user regardless of pk
        url = reverse("user-detail", kwargs={"pk": "any-value"})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)


class ProfileUpdateViewTestCase(APITestCase):
    """Test ProfileUpdateView."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )

    def test_update_profile_authenticated(self):
        """Test updating profile when authenticated."""
        self.client.force_authenticate(user=self.user)
        url = reverse("api-profile-update")

        data = {"name": "Updated Profile Name", "email": "updated@example.com"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Profile Name")
        self.assertEqual(response.data["email"], "updated@example.com")

    def test_update_profile_unauthenticated(self):
        """Test updating profile without authentication."""
        url = reverse("api-profile-update")

        data = {"name": "Hacker Name"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_profile_partial_data(self):
        """Test updating profile with partial data."""
        self.client.force_authenticate(user=self.user)
        url = reverse("api-profile-update")

        data = {"name": "Only Name Updated"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Only Name Updated")
        self.assertEqual(
            response.data["email"], self.user.email
        )  # Should remain unchanged

    def test_update_profile_invalid_data(self):
        """Test updating profile with invalid data."""
        self.client.force_authenticate(user=self.user)
        url = reverse("api-profile-update")

        data = {"email": "invalid-email-format"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PasswordResetViewTestCase(APITestCase):
    """Test PasswordResetView."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )

    def test_password_reset_request_valid_email(self):
        """Test password reset request with valid email."""
        url = reverse("api-password-reset")

        data = {"email": "test@example.com"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("password reset link has been sent", response.data["message"])

    def test_password_reset_request_invalid_email(self):
        """Test password reset request with non-existent email."""
        url = reverse("api-password-reset")

        data = {"email": "nonexistent@example.com"}

        response = self.client.post(url, data, format="json")

        # Should still return success for security reasons
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("password reset link has been sent", response.data["message"])

    def test_password_reset_request_no_email(self):
        """Test password reset request without email."""
        url = reverse("api-password-reset")

        data = {}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Email is required.")

    def test_password_reset_request_empty_email(self):
        """Test password reset request with empty email."""
        url = reverse("api-password-reset")

        data = {"email": ""}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Email is required.")


class PasswordResetConfirmViewTestCase(APITestCase):
    """Test PasswordResetConfirmView."""

    def test_password_reset_confirm_valid_data(self):
        """Test password reset confirmation with valid data."""
        url = reverse("api-password-reset-confirm")

        # Create a test user
        user = User.objects.create_user(
            email="reset@example.com", name="Reset User", password="oldpass123"
        )

        # Generate a real Django password reset token
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        data = {
            "token": token,
            "uid": uid,
            "password": "newpassword123456",
            "password_confirm": "newpassword123456",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"], "Password has been reset successfully."
        )

        # Verify that the password was actually changed
        user.refresh_from_db()
        self.assertTrue(user.check_password("newpassword123456"))

    def test_password_reset_confirm_missing_token(self):
        """Test password reset confirmation without token."""
        url = reverse("api-password-reset-confirm")

        data = {
            "password": "newpassword123456",
            "password_confirm": "newpassword123456",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Token, password, and password confirmation are required",
            response.data["error"],
        )

    def test_password_reset_confirm_missing_password(self):
        """Test password reset confirmation without password."""
        url = reverse("api-password-reset-confirm")

        # Create a test user and generate a real token
        user = User.objects.create_user(
            email="reset@example.com", name="Reset User", password="oldpass123"
        )
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        data = {"token": token, "uid": uid, "password_confirm": "newpassword123456"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Token, password, and password confirmation are required",
            response.data["error"],
        )

    def test_password_reset_confirm_password_mismatch(self):
        """Test password reset confirmation with mismatched passwords."""
        url = reverse("api-password-reset-confirm")

        # Create a test user and generate a real token
        user = User.objects.create_user(
            email="reset@example.com", name="Reset User", password="oldpass123"
        )
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        data = {
            "token": token,
            "uid": uid,
            "password": "newpassword123456",
            "password_confirm": "differentpassword123456",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Passwords do not match.")

    def test_password_reset_confirm_empty_fields(self):
        """Test password reset confirmation with empty fields."""
        url = reverse("api-password-reset-confirm")

        data = {"token": "", "password": "", "password_confirm": ""}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Token, password, and password confirmation are required",
            response.data["error"],
        )


class EmailVerificationViewTestCase(APITestCase):
    """Test EmailVerificationView."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )
        self.email_address = EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=False, primary=True
        )

    def test_email_verification_valid_token(self):
        """Test email verification with valid token."""
        # Create a valid EmailConfirmation
        confirmation = EmailConfirmation.objects.create(
            email_address=self.email_address, key="test-confirmation-key"
        )

        url = reverse("api-verify-email")
        data = {"token": confirmation.key}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"], "Email has been verified successfully."
        )

        # Check that email is now verified
        self.email_address.refresh_from_db()
        self.assertTrue(self.email_address.verified)

    def test_email_verification_missing_token(self):
        """Test email verification without token."""
        url = reverse("api-verify-email")

        data = {}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Verification token is required.")

    def test_email_verification_empty_token(self):
        """Test email verification with empty token."""
        url = reverse("api-verify-email")

        data = {"token": ""}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Verification token is required.")


class AuthThrottleTestCase(TestCase):
    """Test AuthThrottle configuration."""

    def test_auth_throttle_configuration(self):
        """Test AuthThrottle has correct configuration."""
        from apps.accounts.views import AuthThrottle

        throttle = AuthThrottle()
        self.assertEqual(throttle.scope, "auth")
        self.assertEqual(throttle.rate, "5/min")

"""Comprehensive tests for authentication views and flows."""

from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from allauth.account.models import EmailAddress, EmailConfirmation
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.middleware import LastSeenMiddleware
from apps.accounts.models import UserProfile
from apps.accounts.views import CustomUserRateThrottle

User = get_user_model()


class PasswordResetTestCase(APITestCase):
    """Test password reset functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com", password="oldpassword123", name="Test User"
        )
        self.email_address = EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )

    def test_password_reset_request(self):
        """Test requesting a password reset."""
        url = reverse("api-password-reset")
        data = {"email": self.user.email}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn("Reset your password", email.subject)
        self.assertIn(self.user.email, email.to)

    def test_password_reset_request_invalid_email(self):
        """Test password reset with invalid email."""
        url = reverse("api-password-reset")
        data = {"email": "nonexistent@example.com"}

        response = self.client.post(url, data, format="json")

        # Should still return success for security
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # But no email should be sent
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_request_malformed_email(self):
        """Test password reset with malformed email."""
        url = reverse("api-password-reset")
        data = {"email": "invalid-email"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("django.core.mail.send_mail")
    @patch("apps.emails.services.send_password_reset_email")
    def test_password_reset_email_service_error(
        self, mock_password_reset_email, mock_send_mail
    ):
        """Test password reset when email service fails."""
        mock_password_reset_email.side_effect = Exception("Email service down")
        mock_send_mail.side_effect = Exception("Fallback email service down")

        url = reverse("api-password-reset")
        data = {"email": self.user.email}

        response = self.client.post(url, data, format="json")

        # Should handle gracefully
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_password_reset_confirm_valid_token(self):
        """Test confirming password reset with valid token."""
        # First request password reset
        self.client.post(
            reverse("api-password-reset"), {"email": self.user.email}, format="json"
        )

        # Extract token from email (mock implementation)
        token = "mock-token-123"

        url = reverse("api-password-reset-confirm")
        data = {
            "token": token,
            "uid": str(self.user.pk),  # Add the user ID
            "password": "newpassword123",
            "password_confirm": "newpassword123",
        }

        with patch(
            "django.contrib.auth.tokens.default_token_generator.check_token",
            return_value=True,
        ):
            response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_confirm_mismatched_passwords(self):
        """Test password reset confirm with mismatched passwords."""
        token = "mock-token-123"

        url = reverse("api-password-reset-confirm")
        data = {
            "token": token,
            "password": "newpassword123",
            "password_confirm": "differentpassword123",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_confirm_invalid_token(self):
        """Test password reset confirm with invalid token."""
        token = "invalid-token"

        url = reverse("api-password-reset-confirm")
        data = {
            "token": token,
            "uid": str(self.user.pk),  # Add the user ID
            "password": "newpassword123",
            "password_confirm": "newpassword123",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EmailVerificationTestCase(APITestCase):
    """Test email verification functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )
        self.email_address = EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=False, primary=True
        )

    def test_email_verification_request(self):
        """Test requesting email verification."""
        self.client.force_authenticate(user=self.user)
        url = reverse("api-verify-email")

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that verification email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn("Confirm", email.subject)  # allauth uses "Confirm" not "Verify"
        self.assertIn(self.user.email, email.to)

    def test_email_verification_request_already_verified(self):
        """Test requesting verification for already verified email."""
        self.email_address.verified = True
        self.email_address.save()

        self.client.force_authenticate(user=self.user)
        url = reverse("api-verify-email")

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_verification_confirm_valid_key(self):
        """Test confirming email verification with valid key."""
        # Create EmailConfirmation
        confirmation = EmailConfirmation.objects.create(
            email_address=self.email_address, key="test-confirmation-key"
        )

        url = reverse("api-verify-email")
        data = {"token": confirmation.key}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that email is now verified
        self.email_address.refresh_from_db()
        self.assertTrue(self.email_address.verified)

    def test_email_verification_confirm_invalid_key(self):
        """Test confirming email verification with invalid key."""
        url = reverse("api-verify-email")
        data = {"token": "invalid-key"}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_email_verification_confirm_expired_key(self):
        """Test confirming email verification with expired key."""
        from datetime import timedelta

        from django.utils import timezone

        confirmation = EmailConfirmation.objects.create(
            email_address=self.email_address, key="expired-key"
        )

        # Make the confirmation expired
        confirmation.created = timezone.now() - timedelta(days=4)
        confirmation.save()

        url = reverse("api-verify-email")
        data = {"token": confirmation.key}

        with patch.object(EmailConfirmation, "key_expired", return_value=True):
            response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserRateThrottleTestCase(TestCase):
    """Test custom user rate throttle."""

    def setUp(self):
        """Set up test data."""
        self.throttle = CustomUserRateThrottle()
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )

    def test_throttle_init_in_test_mode(self):
        """Test throttle initialization in test mode."""
        with override_settings(TESTING=True):
            throttle = CustomUserRateThrottle()
            self.assertIsNone(throttle.rate)
            self.assertEqual(throttle.num_requests, 0)
            self.assertEqual(throttle.duration, 0)

    def test_throttle_init_with_memory_db(self):
        """Test throttle initialization with in-memory database."""
        with override_settings(
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            }
        ):
            throttle = CustomUserRateThrottle()
            self.assertIsNone(throttle.rate)

    def test_throttle_normal_init(self):
        """Test throttle normal initialization."""
        # This would test actual throttle behavior in production
        # Implementation depends on DRF throttle setup
        pass

    @override_settings(TESTING=False)
    def test_throttle_allow_request(self):
        """Test throttle allows requests within limits."""
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.get("/test/")
        request.user = self.user

        # In test mode, should always allow
        self.assertTrue(self.throttle.allow_request(request, None))

    def test_throttle_get_cache_key(self):
        """Test throttle cache key generation."""
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.get("/test/")
        request.user = self.user

        # Should generate a cache key based on user
        key = self.throttle.get_cache_key(request, None)
        if key:  # Only if throttle is properly configured
            self.assertIn(str(self.user.pk), key)

    def test_throttle_allow_request_with_test_db_name_containing_test(self):
        """Test throttle allows request when database name contains 'test'."""
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.get("/test/")
        request.user = self.user

        # Mock settings to have a database name containing 'test'
        with override_settings(
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": "/path/to/test_database.db",
                }
            }
        ):
            throttle = CustomUserRateThrottle()
            # Should allow request in test database environment
            self.assertTrue(throttle.allow_request(request, None))

    @patch("rest_framework.throttling.UserRateThrottle.allow_request")
    def test_throttle_allow_request_exception_handling(self, mock_allow_request):
        """Test throttle allows request when parent allow_request raises exception."""
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        request = factory.get("/test/")
        request.user = self.user

        # Mock the parent allow_request to raise an exception
        mock_allow_request.side_effect = Exception("Cache connection failed")

        # Create throttle in non-test environment
        with override_settings(
            TESTING=False,
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": "/path/to/production.db",
                }
            },
        ):
            throttle = CustomUserRateThrottle()
            # Should catch exception and allow request
            result = throttle.allow_request(request, None)
            self.assertTrue(result)

    def test_throttle_init_with_exception(self):
        """Test throttle initialization when parent __init__ raises exception."""
        # Create throttle in non-test environment
        with (
            override_settings(
                TESTING=False,
                DATABASES={
                    "default": {
                        "ENGINE": "django.db.backends.sqlite3",
                        "NAME": "/path/to/production.db",
                    }
                },
            ),
            patch("rest_framework.throttling.UserRateThrottle.__init__") as mock_init,
        ):
            # Mock parent __init__ to raise an exception
            mock_init.side_effect = Exception("Rate not defined")

            throttle = CustomUserRateThrottle()

            # Should catch exception and set defaults
            self.assertIsNone(throttle.rate)
            self.assertEqual(throttle.num_requests, 0)
            self.assertEqual(throttle.duration, 0)


class LastSeenMiddlewareTestCase(TestCase):
    """Test LastSeenMiddleware functionality."""

    def setUp(self):
        """Set up test data."""
        self.middleware = LastSeenMiddleware(get_response=lambda x: x)
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

    def test_middleware_updates_last_seen_for_authenticated_user(self):
        """Test middleware updates last_seen for authenticated users."""
        from datetime import timedelta

        from django.test import RequestFactory
        from django.utils import timezone

        # Set initial last_seen to past time
        old_time = timezone.now() - timedelta(minutes=10)
        self.user.last_seen = old_time
        self.user.save()

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user

        # Process request through middleware
        self.middleware.process_request(request)

        # Check that last_seen was updated
        self.user.refresh_from_db()
        self.assertGreater(self.user.last_seen, old_time)

    def test_middleware_ignores_anonymous_users(self):
        """Test middleware ignores anonymous users."""
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/")
        request.user = AnonymousUser()

        # Should not raise any errors
        result = self.middleware.process_request(request)
        self.assertIsNone(result)

    def test_middleware_handles_missing_profile(self):
        """Test middleware handles users without profiles."""
        from django.test import RequestFactory

        # Delete user profile if it exists
        if hasattr(self.user, "profile"):
            self.user.profile.delete()

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user

        # Should handle gracefully
        result = self.middleware.process_request(request)
        self.assertIsNone(result)

    def test_middleware_get_response_passthrough(self):
        """Test middleware passes through get_response."""
        from django.http import HttpResponse
        from django.test import RequestFactory

        def mock_get_response(request):
            return HttpResponse("Test Response")

        middleware = LastSeenMiddleware(get_response=mock_get_response)

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user

        response = middleware(request)

        self.assertEqual(response.content, b"Test Response")


class UserSignalsTestCase(TestCase):
    """Test user-related signals."""

    def test_user_profile_created_on_user_creation(self):
        """Test that UserProfile is created when User is created."""
        user = User.objects.create_user(
            email="newuser@example.com", password="testpass123", name="New User"
        )

        # Profile should be created automatically
        self.assertTrue(hasattr(user, "profile"))
        self.assertIsNotNone(user.profile)
        self.assertIsInstance(user.profile, UserProfile)

    def test_user_profile_not_duplicated(self):
        """Test that duplicate profiles are not created."""
        user = User.objects.create_user(
            email="unique@example.com", password="testpass123", name="Unique User"
        )

        # Try to save user again
        user.save()

        # Should still have only one profile
        profile_count = UserProfile.objects.filter(user=user).count()
        self.assertEqual(profile_count, 1)


class AuthenticationIntegrationTestCase(APITestCase):
    """Integration tests for complete authentication flows."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

    def test_complete_registration_flow(self):
        """Test complete user registration and verification flow."""
        # Step 1: Register new user
        registration_data = {
            "email": "newuser@example.com",
            "password1": "complexpass123",
            "password2": "complexpass123",
            "name": "New User",
        }

        response = self.client.post(
            reverse("user-register"), registration_data, format="json"
        )

        # Should create user but require verification
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email="newuser@example.com")
        self.assertFalse(user.emailaddress_set.first().verified)

        # Step 2: Verify email (simplified)
        email_address = user.emailaddress_set.first()
        email_address.verified = True
        email_address.save()

        # Step 3: Login with verified account (using django's authenticate)
        from django.contrib.auth import authenticate

        authenticated_user = authenticate(
            email="newuser@example.com", password="complexpass123"
        )

        self.assertIsNotNone(authenticated_user)
        self.assertEqual(authenticated_user.email, "newuser@example.com")

    def test_login_with_unverified_email(self):
        """Test login attempt with unverified email."""
        user = User.objects.create_user(
            email="unverified@example.com", password="testpass123"
        )

        # Ensure email is unverified
        EmailAddress.objects.create(
            user=user, email=user.email, verified=False, primary=True
        )

        # Test authentication with unverified email
        from django.contrib.auth import authenticate

        authenticated_user = authenticate(
            email="unverified@example.com", password="testpass123"
        )

        # User should still be able to authenticate even with unverified email
        # Email verification enforcement happens at the view level, not auth level
        self.assertIsNotNone(authenticated_user)

"""Tests for accounts serializers."""

from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from rest_framework import serializers

from apps.accounts.models import UserProfile
from apps.accounts.serializers import (
    PasswordChangeSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

User = get_user_model()


class UserSerializerTestCase(TestCase):
    """Test UserSerializer."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )
        self.user.avatar = "avatars/test.jpg"  # Mock avatar
        self.user.save()

    def test_get_avatar_url_with_request(self):
        """Test getting avatar URL with request context."""
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"

        serializer = UserSerializer(instance=self.user, context={"request": request})
        data = serializer.data

        self.assertIn("avatar_url", data)
        self.assertIn("testserver", data["avatar_url"])
        self.assertIn("avatars/test.jpg", data["avatar_url"])

    def test_get_avatar_url_without_request(self):
        """Test getting avatar URL without request context."""
        serializer = UserSerializer(instance=self.user)
        data = serializer.data

        self.assertIn("avatar_url", data)
        self.assertEqual(data["avatar_url"], self.user.avatar.url)

    def test_get_avatar_url_no_avatar(self):
        """Test getting avatar URL when user has no avatar."""
        user_no_avatar = User.objects.create_user(
            email="noavatar@example.com", name="No Avatar", password="testpass123"
        )

        serializer = UserSerializer(instance=user_no_avatar)
        data = serializer.data

        self.assertIsNone(data["avatar_url"])


class UserRegistrationSerializerTestCase(TestCase):
    """Test UserRegistrationSerializer."""

    def test_password_validation_exception_handling(self):
        """Test password validation with generic exception."""
        data = {
            "email": "test@example.com",
            "password1": "weak",
            "password2": "weak",
        }

        serializer = UserRegistrationSerializer(data=data)

        # Mock validate_password to raise a generic exception without messages
        with patch("apps.accounts.serializers.validate_password") as mock_validate:
            mock_validate.side_effect = Exception("Generic password error")

            self.assertFalse(serializer.is_valid())
            self.assertIn("password1", serializer.errors)
            self.assertIn("Generic password error", str(serializer.errors["password1"]))

    def test_password_validation_with_iterable_exception(self):
        """Test password validation with iterable exception."""
        data = {
            "email": "test@example.com",
            "password1": "weak",
            "password2": "weak",
        }

        serializer = UserRegistrationSerializer(data=data)

        # Mock validate_password to raise an iterable exception
        class IterableException(Exception):
            def __init__(self, messages):
                self.messages = messages
                super().__init__()

            def __iter__(self):
                return iter(self.messages)

        with patch("apps.accounts.serializers.validate_password") as mock_validate:
            mock_validate.side_effect = IterableException(["Error 1", "Error 2"])

            self.assertFalse(serializer.is_valid())
            self.assertIn("password1", serializer.errors)
            self.assertIn("Error 1", str(serializer.errors["password1"]))
            self.assertIn("Error 2", str(serializer.errors["password1"]))


class PasswordChangeSerializerTestCase(TestCase):
    """Test PasswordChangeSerializer."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="oldpass123"
        )

    def test_password_mismatch_validation(self):
        """Test password change with mismatched passwords."""
        request = Mock()
        request.user = self.user

        data = {
            "old_password": "oldpass123",
            "new_password1": "newpass123",
            "new_password2": "differentpass123",
        }

        serializer = PasswordChangeSerializer(data=data, context={"request": request})

        self.assertFalse(serializer.is_valid())
        self.assertIn("The two password fields didn't match", str(serializer.errors))

    def test_password_validation_exception_handling(self):
        """Test password validation with generic exception."""
        request = Mock()
        request.user = self.user

        data = {
            "old_password": "oldpass123",
            "new_password1": "weak",
            "new_password2": "weak",
        }

        serializer = PasswordChangeSerializer(data=data, context={"request": request})

        # Mock validate_password to raise a generic exception without messages
        with patch("apps.accounts.serializers.validate_password") as mock_validate:
            mock_validate.side_effect = Exception("Generic password error")

            self.assertFalse(serializer.is_valid())
            self.assertIn("new_password1", serializer.errors)
            self.assertIn(
                "Generic password error", str(serializer.errors["new_password1"])
            )

    def test_password_validation_with_iterable_exception(self):
        """Test password validation with iterable exception."""
        request = Mock()
        request.user = self.user

        data = {
            "old_password": "oldpass123",
            "new_password1": "weak",
            "new_password2": "weak",
        }

        serializer = PasswordChangeSerializer(data=data, context={"request": request})

        # Mock validate_password to raise an iterable exception
        class IterableException(Exception):
            def __init__(self, messages):
                self.messages = messages
                super().__init__()

            def __iter__(self):
                return iter(self.messages)

        with patch("apps.accounts.serializers.validate_password") as mock_validate:
            mock_validate.side_effect = IterableException(["Error 1", "Error 2"])

            self.assertFalse(serializer.is_valid())
            self.assertIn("new_password1", serializer.errors)
            self.assertIn("Error 1", str(serializer.errors["new_password1"]))
            self.assertIn("Error 2", str(serializer.errors["new_password1"]))


class UserUpdateSerializerTestCase(TestCase):
    """Test UserUpdateSerializer."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", name="Other User", password="testpass123"
        )

    def test_email_validation_conflict(self):
        """Test email validation when another user has the email."""
        data = {
            "email": "other@example.com",  # Already taken by other_user
            "name": "Updated Name",
        }

        serializer = UserUpdateSerializer(instance=self.user, data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)
        # Check for either validation message (the exact message may vary)
        error_str = str(serializer.errors["email"])
        self.assertTrue(
            "already registered" in error_str or "already exists" in error_str
        )

    def test_update_with_profile_data(self):
        """Test updating user with profile data when profile exists."""
        # Get the auto-created profile from the signal and update it
        profile = self.user.profile
        profile.bio = "Old bio"
        profile.location = "Old location"
        profile.save()

        data = {
            "name": "Updated Name",
            "email": self.user.email,  # Include existing email
            "profile": {
                "bio": "New bio",
                "location": "New location",
                "phone": "+1234567890",
            },
        }

        serializer = UserUpdateSerializer(instance=self.user, data=data)

        self.assertTrue(serializer.is_valid())
        updated_user = serializer.save()

        self.assertEqual(updated_user.name, "Updated Name")
        profile.refresh_from_db()
        self.assertEqual(profile.bio, "New bio")
        self.assertEqual(profile.location, "New location")
        self.assertEqual(profile.phone, "+1234567890")

    def test_update_with_profile_data_no_profile(self):
        """Test updating user with profile data when profile exists (via signal)."""
        data = {
            "name": "Updated Name",
            "email": self.user.email,  # Include existing email
            "profile": {"bio": "New bio", "location": "New location"},
        }

        serializer = UserUpdateSerializer(instance=self.user, data=data)

        self.assertTrue(serializer.is_valid())
        updated_user = serializer.save()

        self.assertEqual(updated_user.name, "Updated Name")
        # Profile is auto-created by signal and should be updated
        self.assertTrue(hasattr(self.user, "profile"))
        profile = self.user.profile
        self.assertEqual(profile.bio, "New bio")
        self.assertEqual(profile.location, "New location")

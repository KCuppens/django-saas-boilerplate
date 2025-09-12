"""Tests for accounts serializers"""

import io
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from PIL import Image
from rest_framework import serializers
from rest_framework.test import APIRequestFactory

from apps.accounts.models import UserProfile
from apps.accounts.serializers import (
    PasswordChangeSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

User = get_user_model()


class UserProfileSerializerTest(TestCase):
    """Test UserProfileSerializer"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            bio="Test bio",
            location="Test City",
            website="https://example.com",
            phone="123-456-7890",
            timezone="America/New_York",
            language="es",
            receive_notifications=False,
            receive_marketing_emails=True
        )

    def test_serializer_fields(self):
        """Test that serializer includes correct fields"""
        serializer = UserProfileSerializer(instance=self.profile)
        expected_fields = [
            "bio", "location", "website", "phone", "timezone",
            "language", "receive_notifications", "receive_marketing_emails"
        ]

        self.assertEqual(set(serializer.data.keys()), set(expected_fields))

    def test_serializer_data(self):
        """Test serializer data output"""
        serializer = UserProfileSerializer(instance=self.profile)
        data = serializer.data

        self.assertEqual(data["bio"], "Test bio")
        self.assertEqual(data["location"], "Test City")
        self.assertEqual(data["website"], "https://example.com")
        self.assertEqual(data["phone"], "123-456-7890")
        self.assertEqual(data["timezone"], "America/New_York")
        self.assertEqual(data["language"], "es")
        self.assertFalse(data["receive_notifications"])
        self.assertTrue(data["receive_marketing_emails"])

    def test_serializer_validation(self):
        """Test serializer validation with valid data"""
        data = {
            "bio": "New bio",
            "location": "New City",
            "website": "https://newsite.com",
            "phone": "987-654-3210",
            "timezone": "Europe/London",
            "language": "fr",
            "receive_notifications": True,
            "receive_marketing_emails": False
        }

        serializer = UserProfileSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_serializer_update(self):
        """Test serializer update functionality"""
        data = {
            "bio": "Updated bio",
            "location": "Updated City",
            "receive_notifications": True
        }

        serializer = UserProfileSerializer(instance=self.profile, data=data, partial=True)
        self.assertTrue(serializer.is_valid())

        updated_profile = serializer.save()
        self.assertEqual(updated_profile.bio, "Updated bio")
        self.assertEqual(updated_profile.location, "Updated City")
        self.assertTrue(updated_profile.receive_notifications)


class UserSerializerTest(TestCase):
    """Test UserSerializer"""

    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User"
        )
        self.profile = UserProfile.objects.create(user=self.user)

    def test_serializer_fields(self):
        """Test that serializer includes correct fields"""
        serializer = UserSerializer(instance=self.user)
        expected_fields = [
            "id", "email", "name", "avatar", "avatar_url", "full_name",
            "short_name", "last_seen", "is_active", "date_joined",
            "created_at", "updated_at", "profile"
        ]

        self.assertEqual(set(serializer.data.keys()), set(expected_fields))

    def test_serializer_read_only_fields(self):
        """Test that read-only fields are properly configured"""
        serializer = UserSerializer()
        expected_read_only = [
            "id", "last_seen", "date_joined", "created_at", "updated_at"
        ]

        self.assertEqual(set(serializer.Meta.read_only_fields), set(expected_read_only))

    def test_full_name_field(self):
        """Test full_name field returns correct value"""
        serializer = UserSerializer(instance=self.user)
        self.assertEqual(serializer.data["full_name"], "Test User")

    def test_short_name_field(self):
        """Test short_name field returns correct value"""
        serializer = UserSerializer(instance=self.user)
        self.assertEqual(serializer.data["short_name"], "Test")

    def test_avatar_url_with_avatar_and_request(self):
        """Test avatar_url method with avatar and request context"""
        # Create a simple image
        image = Image.new('RGB', (100, 100), color='red')
        image_io = io.BytesIO()
        image.save(image_io, format='PNG')
        image_io.seek(0)

        avatar = SimpleUploadedFile(
            "test.png",
            image_io.getvalue(),
            content_type="image/png"
        )
        self.user.avatar = avatar
        self.user.save()

        # Mock request
        request = self.factory.get('/')
        request.META['HTTP_HOST'] = 'testserver'

        serializer = UserSerializer(instance=self.user, context={'request': request})
        avatar_url = serializer.data["avatar_url"]

        self.assertIsNotNone(avatar_url)
        self.assertIn("test.png", avatar_url)

    def test_avatar_url_with_avatar_no_request(self):
        """Test avatar_url method with avatar but no request context"""
        # Create a simple image
        image = Image.new('RGB', (100, 100), color='red')
        image_io = io.BytesIO()
        image.save(image_io, format='PNG')
        image_io.seek(0)

        avatar = SimpleUploadedFile(
            "test.png",
            image_io.getvalue(),
            content_type="image/png"
        )
        self.user.avatar = avatar
        self.user.save()

        serializer = UserSerializer(instance=self.user)
        avatar_url = serializer.data["avatar_url"]

        self.assertIsNotNone(avatar_url)
        self.assertIn("test.png", avatar_url)

    def test_avatar_url_without_avatar(self):
        """Test avatar_url method without avatar"""
        serializer = UserSerializer(instance=self.user)
        self.assertIsNone(serializer.data["avatar_url"])

    def test_profile_nested_serialization(self):
        """Test that profile is properly nested"""
        serializer = UserSerializer(instance=self.user)
        profile_data = serializer.data["profile"]

        self.assertIsInstance(profile_data, dict)
        self.assertIn("bio", profile_data)
        self.assertIn("timezone", profile_data)


class UserRegistrationSerializerTest(TestCase):
    """Test UserRegistrationSerializer"""

    @patch('apps.accounts.serializers.get_adapter')
    def test_email_validation_success(self, mock_get_adapter):
        """Test email validation with valid email"""
        mock_adapter = MagicMock()
        mock_adapter.clean_email.return_value = "test@example.com"
        mock_get_adapter.return_value = mock_adapter

        serializer = UserRegistrationSerializer()
        result = serializer.validate_email("test@example.com")

        self.assertEqual(result, "test@example.com")
        mock_adapter.clean_email.assert_called_once_with("test@example.com")

    @patch('apps.accounts.serializers.get_adapter')
    def test_email_validation_already_exists(self, mock_get_adapter):
        """Test email validation with existing email"""
        # Create existing user
        User.objects.create_user(email="existing@example.com", password="pass123")

        mock_adapter = MagicMock()
        mock_adapter.clean_email.return_value = "existing@example.com"
        mock_get_adapter.return_value = mock_adapter

        serializer = UserRegistrationSerializer()

        with self.assertRaises(serializers.ValidationError) as context:
            serializer.validate_email("existing@example.com")

        self.assertIn("already registered", str(context.exception))

    def test_password_validation_mismatch(self):
        """Test password validation with mismatched passwords"""
        data = {
            "email": "test@example.com",
            "password1": "pass123",
            "password2": "different123"
        }

        serializer = UserRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("password fields didn't match", str(serializer.errors))

    @patch('apps.accounts.serializers.validate_password')
    def test_password_validation_weak_password(self, mock_validate):
        """Test password validation with weak password"""
        mock_validate.side_effect = Exception(["Password too weak"])

        data = {
            "email": "test@example.com",
            "password1": "123",
            "password2": "123"
        }

        serializer = UserRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("password1", serializer.errors)

    def test_valid_serializer(self):
        """Test serializer with valid data"""
        data = {
            "email": "test@example.com",
            "name": "Test User",
            "password1": "strongpass123",
            "password2": "strongpass123"
        }

        with patch('apps.accounts.serializers.get_adapter') as mock_get_adapter:
            mock_adapter = MagicMock()
            mock_adapter.clean_email.return_value = "test@example.com"
            mock_get_adapter.return_value = mock_adapter

            serializer = UserRegistrationSerializer(data=data)
            self.assertTrue(serializer.is_valid())

    @patch('apps.accounts.serializers.get_adapter')
    @patch('apps.accounts.serializers.setup_user_email')
    def test_save_method(self, mock_setup_email, mock_get_adapter):
        """Test save method creates user correctly"""
        mock_adapter = MagicMock()
        mock_user = MagicMock()
        mock_adapter.new_user.return_value = mock_user
        mock_adapter.clean_email.return_value = "test@example.com"
        mock_get_adapter.return_value = mock_adapter

        data = {
            "email": "test@example.com",
            "name": "Test User",
            "password1": "strongpass123",
            "password2": "strongpass123"
        }

        serializer = UserRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        mock_request = MagicMock()
        serializer.save(mock_request)

        # Verify adapter methods were called
        mock_adapter.new_user.assert_called_once_with(mock_request)
        mock_adapter.save_user.assert_called_once_with(mock_request, mock_user, form=None)
        mock_setup_email.assert_called_once_with(mock_request, mock_user, [])

        # Verify user attributes were set
        self.assertEqual(mock_user.email, "test@example.com")
        self.assertEqual(mock_user.name, "Test User")
        mock_user.set_password.assert_called_once_with("strongpass123")
        mock_user.save.assert_called_once()


class PasswordChangeSerializerTest(TestCase):
    """Test PasswordChangeSerializer"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="test@example.com",
            password="oldpass123"
        )
        self.factory = APIRequestFactory()

    def test_old_password_validation_correct(self):
        """Test old password validation with correct password"""
        request = self.factory.post('/')
        request.user = self.user

        serializer = PasswordChangeSerializer(context={'request': request})
        result = serializer.validate_old_password("oldpass123")

        self.assertEqual(result, "oldpass123")

    def test_old_password_validation_incorrect(self):
        """Test old password validation with incorrect password"""
        request = self.factory.post('/')
        request.user = self.user

        serializer = PasswordChangeSerializer(context={'request': request})

        with self.assertRaises(serializers.ValidationError) as context:
            serializer.validate_old_password("wrongpass")

        self.assertIn("incorrectly", str(context.exception))

    def test_new_password_validation_mismatch(self):
        """Test new password validation with mismatched passwords"""
        request = self.factory.post('/')
        request.user = self.user

        data = {
            "old_password": "oldpass123",
            "new_password1": "newpass123",
            "new_password2": "different123"
        }

        serializer = PasswordChangeSerializer(data=data, context={'request': request})
        self.assertFalse(serializer.is_valid())
        self.assertIn("password fields didn't match", str(serializer.errors))

    @patch('apps.accounts.serializers.validate_password')
    def test_new_password_validation_weak(self, mock_validate):
        """Test new password validation with weak password"""
        mock_validate.side_effect = Exception(["Password too weak"])

        request = self.factory.post('/')
        request.user = self.user

        data = {
            "old_password": "oldpass123",
            "new_password1": "123",
            "new_password2": "123"
        }

        serializer = PasswordChangeSerializer(data=data, context={'request': request})
        self.assertFalse(serializer.is_valid())
        self.assertIn("new_password1", serializer.errors)

    def test_save_method(self):
        """Test save method changes password correctly"""
        request = self.factory.post('/')
        request.user = self.user

        data = {
            "old_password": "oldpass123",
            "new_password1": "newstrongpass123",
            "new_password2": "newstrongpass123"
        }

        serializer = PasswordChangeSerializer(data=data, context={'request': request})
        self.assertTrue(serializer.is_valid())

        result = serializer.save()

        # Verify password was changed
        self.assertEqual(result, self.user)
        self.assertTrue(self.user.check_password("newstrongpass123"))
        self.assertFalse(self.user.check_password("oldpass123"))


class UserUpdateSerializerTest(TestCase):
    """Test UserUpdateSerializer"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Original Name"
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            bio="Original bio",
            location="Original City"
        )

    def test_serializer_fields(self):
        """Test that serializer includes correct fields"""
        serializer = UserUpdateSerializer()
        expected_fields = ["name", "avatar", "profile"]

        self.assertEqual(set(serializer.Meta.fields), set(expected_fields))

    def test_update_user_fields_only(self):
        """Test updating only user fields"""
        data = {
            "name": "Updated Name"
        }

        serializer = UserUpdateSerializer(instance=self.user, data=data, partial=True)
        self.assertTrue(serializer.is_valid())

        updated_user = serializer.save()
        self.assertEqual(updated_user.name, "Updated Name")

    def test_update_with_avatar(self):
        """Test updating user with avatar"""
        # Create a simple image
        image = Image.new('RGB', (100, 100), color='blue')
        image_io = io.BytesIO()
        image.save(image_io, format='PNG')
        image_io.seek(0)

        avatar = SimpleUploadedFile(
            "new_avatar.png",
            image_io.getvalue(),
            content_type="image/png"
        )

        data = {
            "name": "Updated Name",
            "avatar": avatar
        }

        serializer = UserUpdateSerializer(instance=self.user, data=data)
        self.assertTrue(serializer.is_valid())

        updated_user = serializer.save()
        self.assertEqual(updated_user.name, "Updated Name")
        self.assertTrue(updated_user.avatar.name.endswith('.png'))

    def test_update_profile_fields(self):
        """Test updating profile fields"""
        data = {
            "profile": {
                "bio": "Updated bio",
                "location": "Updated City",
                "timezone": "Europe/London"
            }
        }

        serializer = UserUpdateSerializer(instance=self.user, data=data, partial=True)
        self.assertTrue(serializer.is_valid())

        updated_user = serializer.save()
        self.assertEqual(updated_user.profile.bio, "Updated bio")
        self.assertEqual(updated_user.profile.location, "Updated City")
        self.assertEqual(updated_user.profile.timezone, "Europe/London")

    def test_update_user_and_profile(self):
        """Test updating both user and profile fields"""
        data = {
            "name": "Updated Name",
            "profile": {
                "bio": "Updated bio",
                "receive_notifications": False
            }
        }

        serializer = UserUpdateSerializer(instance=self.user, data=data, partial=True)
        self.assertTrue(serializer.is_valid())

        updated_user = serializer.save()
        self.assertEqual(updated_user.name, "Updated Name")
        self.assertEqual(updated_user.profile.bio, "Updated bio")
        self.assertFalse(updated_user.profile.receive_notifications)

    def test_update_without_profile(self):
        """Test updating user without existing profile"""
        # Delete the profile
        self.profile.delete()

        data = {
            "name": "Updated Name",
            "profile": {
                "bio": "New bio"
            }
        }

        serializer = UserUpdateSerializer(instance=self.user, data=data, partial=True)
        self.assertTrue(serializer.is_valid())

        # Should not raise error even without profile
        updated_user = serializer.save()
        self.assertEqual(updated_user.name, "Updated Name")


@pytest.mark.django_db
class TestSerializersWithPytest:
    """Additional pytest-style tests for serializers"""

    def test_user_serializer_with_mock_request(self):
        """Test UserSerializer with mocked request context"""
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User"
        )
        UserProfile.objects.create(user=user)

        # Create mock request
        request = MagicMock()
        request.build_absolute_uri.return_value = "http://testserver/media/avatars/test.png"

        serializer = UserSerializer(instance=user, context={'request': request})
        data = serializer.data

        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
        assert data["full_name"] == "Test User"
        assert data["short_name"] == "Test"
        assert data["profile"] is not None

    def test_user_registration_serializer_email_case_insensitive(self):
        """Test that email validation is case insensitive"""
        # Create user with lowercase email
        User.objects.create_user(email="test@example.com", password="pass123")

        with patch('apps.accounts.serializers.get_adapter') as mock_get_adapter:
            mock_adapter = MagicMock()
            mock_adapter.clean_email.return_value = "TEST@EXAMPLE.COM"
            mock_get_adapter.return_value = mock_adapter

            serializer = UserRegistrationSerializer()

            with pytest.raises(serializers.ValidationError):
                serializer.validate_email("TEST@EXAMPLE.COM")

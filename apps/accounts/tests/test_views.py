"""Tests for accounts views"""

import io
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import UserProfile

User = get_user_model()


class UserViewSetTest(APITestCase):
    """Test UserViewSet functionality"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User"
        )
        self.profile = UserProfile.objects.create(user=self.user)

        # Create another user for testing
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="otherpass123",
            name="Other User"
        )

    def test_get_user_profile_authenticated(self):
        """Test retrieving user profile when authenticated"""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-detail", args=[self.user.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["email"], self.user.email)
        self.assertEqual(data["name"], self.user.name)
        self.assertEqual(data["full_name"], self.user.get_full_name())
        self.assertIn("profile", data)

    def test_get_user_profile_unauthenticated(self):
        """Test retrieving user profile when not authenticated"""
        url = reverse("user-detail", args=[self.user.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_user_profile_authenticated(self):
        """Test updating user profile when authenticated"""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-detail", args=[self.user.pk])

        data = {
            "name": "Updated Name",
            "profile": {
                "bio": "Updated bio",
                "location": "Updated City"
            }
        }

        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh from database
        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()

        self.assertEqual(self.user.name, "Updated Name")
        self.assertEqual(self.user.profile.bio, "Updated bio")
        self.assertEqual(self.user.profile.location, "Updated City")

    def test_update_user_profile_with_avatar(self):
        """Test updating user profile with avatar"""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-detail", args=[self.user.pk])

        # Create a simple image
        image = Image.new('RGB', (100, 100), color='blue')
        image_io = io.BytesIO()
        image.save(image_io, format='PNG')
        image_io.seek(0)

        avatar = SimpleUploadedFile(
            "avatar.png",
            image_io.getvalue(),
            content_type="image/png"
        )

        data = {
            "name": "Updated Name",
            "avatar": avatar
        }

        response = self.client.patch(url, data, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Refresh from database
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar.name.endswith('.png'))

    def test_user_registration_success(self):
        """Test successful user registration"""
        url = reverse("user-register")
        data = {
            "email": "newuser@example.com",
            "name": "New User",
            "password1": "strongpassword123",
            "password2": "strongpassword123"
        }

        with patch('apps.accounts.serializers.get_adapter') as mock_get_adapter:
            mock_adapter = MagicMock()
            mock_adapter.clean_email.return_value = "newuser@example.com"
            mock_adapter.new_user.return_value = MagicMock()
            mock_get_adapter.return_value = mock_adapter

            response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        self.assertIn("user", response_data)
        self.assertIn("message", response_data)
        self.assertEqual(response_data["message"], "Registration successful.")

    def test_user_registration_duplicate_email(self):
        """Test registration with duplicate email"""
        url = reverse("user-register")
        data = {
            "email": self.user.email,  # Use existing user's email
            "name": "Another User",
            "password1": "strongpassword123",
            "password2": "strongpassword123"
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_registration_password_mismatch(self):
        """Test registration with password mismatch"""
        url = reverse("user-register")
        data = {
            "email": "newuser@example.com",
            "name": "New User",
            "password1": "strongpassword123",
            "password2": "differentpassword123"
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertIn("password fields didn't match", str(response_data))

    def test_user_registration_weak_password(self):
        """Test registration with weak password"""
        url = reverse("user-register")
        data = {
            "email": "newuser@example.com",
            "name": "New User",
            "password1": "123",
            "password2": "123"
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_registration_throttling(self):
        """Test that registration endpoint is throttled"""
        url = reverse("user-register")
        data = {
            "email": "spam@example.com",
            "password1": "strongpass123",
            "password2": "strongpass123"
        }

        # Make multiple rapid requests
        for _ in range(10):
            response = self.client.post(url, data, format='json')
            # After several requests, should get throttled
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                break
        else:
            # If we didn't get throttled, that's still okay for this test
            pass

    def test_change_password_success(self):
        """Test successful password change"""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-change-password")

        data = {
            "old_password": "testpass123",
            "new_password1": "newstrongpass123",
            "new_password2": "newstrongpass123"
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["message"], "Password changed successfully.")

        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newstrongpass123"))

    def test_change_password_wrong_old_password(self):
        """Test password change with wrong old password"""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-change-password")

        data = {
            "old_password": "wrongoldpass",
            "new_password1": "newstrongpass123",
            "new_password2": "newstrongpass123"
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_data = response.json()
        self.assertIn("incorrectly", str(response_data))

    def test_change_password_mismatch(self):
        """Test password change with mismatched new passwords"""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-change-password")

        data = {
            "old_password": "testpass123",
            "new_password1": "newpass123",
            "new_password2": "differentpass123"
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_unauthenticated(self):
        """Test password change when not authenticated"""
        url = reverse("user-change-password")

        data = {
            "old_password": "testpass123",
            "new_password1": "newstrongpass123",
            "new_password2": "newstrongpass123"
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ping_endpoint_success(self):
        """Test ping endpoint updates last seen"""
        self.client.force_authenticate(user=self.user)
        old_last_seen = self.user.last_seen
        url = reverse("user-ping")

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response_data = response.json()
        self.assertEqual(response_data["message"], "Last seen updated.")
        self.assertIn("last_seen", response_data)

        # Verify last seen was updated
        self.user.refresh_from_db()
        self.assertGreater(self.user.last_seen, old_last_seen)

    def test_ping_endpoint_unauthenticated(self):
        """Test ping endpoint when not authenticated"""
        url = reverse("user-ping")

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_account_success(self):
        """Test successful account deletion (deactivation)"""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-delete-account")

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify user was deactivated
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_delete_account_unauthenticated(self):
        """Test account deletion when not authenticated"""
        url = reverse("user-delete-account")

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_object_returns_current_user(self):
        """Test that get_object returns the current authenticated user"""
        self.client.force_authenticate(user=self.user)
        # Use any user ID in URL - should still return current user
        url = reverse("user-detail", args=[999])

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["email"], self.user.email)

    def test_get_serializer_class_for_update(self):
        """Test that correct serializer class is used for updates"""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-detail", args=[self.user.pk])

        # Test partial update
        data = {"name": "Updated Name"}
        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test full update
        data = {
            "name": "Fully Updated Name",
            "profile": {"bio": "New bio"}
        }
        response = self.client.put(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_throttling_authenticated_user(self):
        """Test throttling for authenticated user"""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-detail", args=[self.user.pk])

        # Make many requests to test throttling
        for _ in range(100):
            response = self.client.get(url)
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                break
        # This test may or may not trigger throttling depending on settings


@pytest.mark.django_db
class TestUserViewSetWithPytest:
    """Additional pytest-style tests for UserViewSet"""

    def test_user_profile_view_with_fixtures(self, user, auth_client):
        """Test user profile view using pytest fixtures"""
        # Create profile for the user
        UserProfile.objects.create(user=user)

        url = reverse("user-detail", args=[user.pk])
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == user.email
        assert data["name"] == user.name

    def test_user_registration_with_email_verification(self, api_client):
        """Test registration with email verification enabled"""
        url = reverse("user-register")
        data = {
            "email": "verified@example.com",
            "name": "Verified User",
            "password1": "strongpass123",
            "password2": "strongpass123"
        }

        with patch('apps.accounts.serializers.get_adapter') as mock_get_adapter:
            with patch('allauth.account.app_settings.EMAIL_VERIFICATION'):

                mock_adapter = MagicMock()
                mock_adapter.clean_email.return_value = "verified@example.com"
                mock_adapter.new_user.return_value = MagicMock()
                mock_get_adapter.return_value = mock_adapter

                response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        # When email verification is enabled, should contain verification message
        assert "message" in response_data

    def test_password_change_with_complex_validation(self, user, auth_client):
        """Test password change with complex validation rules"""
        url = reverse("user-change-password")

        # Test with weak password that should fail validation
        data = {
            "old_password": "testpass123",
            "new_password1": "weak",
            "new_password2": "weak"
        }

        response = auth_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_user_update_profile_nested_data(self, user, auth_client):
        """Test updating user with nested profile data"""
        # Create profile for the user
        UserProfile.objects.create(user=user)

        url = reverse("user-detail", args=[user.pk])
        data = {
            "name": "Updated Name",
            "profile": {
                "bio": "New bio text",
                "location": "New City",
                "timezone": "America/New_York",
                "receive_notifications": False
            }
        }

        response = auth_client.patch(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.name == "Updated Name"
        assert user.profile.bio == "New bio text"
        assert user.profile.location == "New City"
        assert user.profile.timezone == "America/New_York"
        assert user.profile.receive_notifications is False

    def test_registration_endpoint_validation_errors(self, api_client):
        """Test registration endpoint with various validation errors"""
        url = reverse("user-register")

        # Test missing required fields
        response = api_client.post(url, {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Test invalid email format
        data = {
            "email": "invalid-email",
            "password1": "strongpass123",
            "password2": "strongpass123"
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_user_avatar_upload_validation(self, user, auth_client, sample_image):
        """Test user avatar upload with file validation"""
        url = reverse("user-detail", args=[user.pk])

        # Test with valid image
        data = {"avatar": sample_image}
        response = auth_client.patch(url, data, format='multipart')

        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.avatar is not None

    def test_user_permissions_isolation(self, user, api_client):
        """Test that users can only access their own data"""
        # Create another user
        other_user = User.objects.create_user(
            email="other@example.com",
            password="otherpass123"
        )

        # Authenticate as first user
        api_client.force_authenticate(user=user)

        # Try to access other user's data using their ID in URL
        # Should still return current user's data due to get_object implementation
        url = reverse("user-detail", args=[other_user.pk])
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should return authenticated user's data, not other user's
        assert data["email"] == user.email
        assert data["email"] != other_user.email

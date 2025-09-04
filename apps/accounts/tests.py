import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserProfile

User = get_user_model()


class UserModelTest(APITestCase):
    """Test User model functionality"""

    def test_create_user(self):
        """Test user creation"""
        user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.name, "Test User")
        self.assertTrue(user.check_password("testpass123"))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)

    def test_user_profile_created(self):
        """Test user profile is created automatically"""
        user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )

        self.assertTrue(hasattr(user, "profile"))
        self.assertIsInstance(user.profile, UserProfile)

    def test_user_string_representation(self):
        """Test user string representation"""
        user = User(email="test@example.com")
        self.assertEqual(str(user), "test@example.com")


class UserAPITest(APITestCase):
    """Test User API endpoints"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

    def test_user_registration(self):
        """Test user registration endpoint"""
        url = reverse("user-register")
        data = {
            "email": "newuser@example.com",
            "password1": "newpass123",
            "password2": "newpass123",
            "name": "New User",
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())

    def test_user_profile_view(self):
        """Test user profile view"""
        self.client.force_authenticate(user=self.user)
        url = reverse("user-detail", args=[self.user.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)


@pytest.fixture
def user():
    """Create a test user"""
    return User.objects.create_user(
        email="test@example.com", password="testpass123", name="Test User"
    )


@pytest.fixture
def admin_user():
    """Create an admin user"""
    user = User.objects.create_user(
        email="admin@example.com",
        password="adminpass123",
        name="Admin User",
        is_staff=True,
        is_superuser=True,
    )
    return user


@pytest.fixture
def auth_client(user):
    """Create an authenticated API client"""
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def celery_eager(settings):
    """Configure Celery to execute tasks synchronously"""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True

from django.contrib.auth import get_user_model

from rest_framework.test import APITestCase

from apps.accounts.models import UserProfile
from apps.accounts.serializers import UserProfileSerializer, UserSerializer

User = get_user_model()


class AccountsTestCase(APITestCase):
    """Test accounts functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",  # nosec B106
            name="Test User",
        )

    def test_user_creation(self):
        """Test user can be created"""
        self.assertEqual(self.user.email, "test@example.com")
        self.assertEqual(self.user.name, "Test User")
        self.assertTrue(self.user.check_password("testpass123"))

    def test_user_profile_creation(self):
        """Test user profile can be created"""
        # Create profile manually since it's not auto-created in this setup
        profile, created = UserProfile.objects.get_or_create(user=self.user)
        self.assertTrue(created)
        self.assertIsInstance(profile, UserProfile)

    def test_user_str(self):
        """Test user string representation"""
        self.assertEqual(str(self.user), "test@example.com")

    def test_get_full_name(self):
        """Test get_full_name method"""
        self.assertEqual(self.user.get_full_name(), "Test User")

    def test_get_short_name(self):
        """Test get_short_name method"""
        self.assertEqual(self.user.get_short_name(), "Test")

    def test_user_profile_str(self):
        """Test user profile string representation"""
        # Create profile manually since it's not auto-created
        from apps.accounts.models import UserProfile

        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        expected = f"{self.user.email} Profile"
        self.assertEqual(str(profile), expected)

    def test_user_serializer(self):
        """Test UserSerializer basic functionality"""
        serializer = UserSerializer(instance=self.user)
        data = serializer.data
        self.assertEqual(data["email"], "test@example.com")
        self.assertEqual(data["name"], "Test User")
        self.assertEqual(data["full_name"], "Test User")

    def test_user_profile_serializer(self):
        """Test UserProfileSerializer functionality"""
        # Create profile first
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        serializer = UserProfileSerializer(instance=profile)
        data = serializer.data
        self.assertIsInstance(data, dict)

    def test_user_manager_create_user(self):
        """Test custom user manager create_user method"""
        user = User.objects.create_user(
            email="test2@example.com", password="testpass123", name="Test User 2"
        )
        self.assertEqual(user.email, "test2@example.com")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_user_manager_create_superuser(self):
        """Test custom user manager create_superuser method"""
        admin = User.objects.create_superuser(
            email="admin@example.com", password="adminpass123", name="Admin User"
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_user_has_groups_methods(self):
        """Test user group checking methods"""
        # These methods should exist even if user doesn't have groups
        self.assertFalse(self.user.is_admin())
        self.assertFalse(self.user.is_manager())
        self.assertFalse(self.user.is_member())
        self.assertTrue(hasattr(self.user, "has_group"))

    def test_user_email_normalization(self):
        """Test user email is normalized"""
        user = User.objects.create_user(
            email="Test.Email@EXAMPLE.COM", password="testpass123"
        )
        self.assertEqual(user.email, "Test.Email@example.com")

    def test_user_without_name_methods(self):
        """Test user methods when name is empty"""
        user = User.objects.create_user(
            email="noname@example.com", password="testpass123"
        )
        # When no name is provided
        self.assertEqual(user.get_full_name(), "noname@example.com")
        self.assertEqual(user.get_short_name(), "noname")

    def test_user_manager_create_user_no_email(self):
        """Test creating user without email raises error"""
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="test123")

    def test_user_manager_create_superuser_no_staff(self):
        """Test creating superuser without is_staff raises error"""
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email="admin@example.com", password="adminpass123", is_staff=False
            )

    def test_user_avatar_field(self):
        """Test user avatar field"""
        # Test that avatar field exists and can be set
        self.assertIsNone(self.user.avatar.name)
        self.assertTrue(hasattr(self.user, "avatar"))

    def test_user_last_seen_default(self):
        """Test user last_seen field has default"""
        self.assertIsNotNone(self.user.last_seen)

    def test_user_timestamps(self):
        """Test user timestamp fields"""
        self.assertIsNotNone(self.user.created_at)
        self.assertIsNotNone(self.user.updated_at)

    def test_user_profile_fields(self):
        """Test UserProfile model fields"""
        from apps.accounts.models import UserProfile

        profile = UserProfile.objects.create(user=self.user)

        # Test default values
        self.assertEqual(profile.bio, "")
        self.assertEqual(profile.location, "")
        self.assertEqual(profile.website, "")

        # Test string representation
        self.assertEqual(str(profile), f"{self.user.email} Profile")

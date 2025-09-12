"""Tests for accounts models"""

import io

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from PIL import Image

from apps.accounts.models import UserProfile

User = get_user_model()


class UserModelTest(TestCase):
    """Test User model functionality"""

    def test_create_user_with_email(self):
        """Test creating a user with email"""
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User"
        )

        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.name, "Test User")
        self.assertTrue(user.check_password("testpass123"))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertIsNotNone(user.created_at)
        self.assertIsNotNone(user.updated_at)
        self.assertIsNotNone(user.last_seen)

    def test_create_user_without_email_raises_error(self):
        """Test creating user without email raises ValueError"""
        with self.assertRaises(ValueError) as context:
            User.objects.create_user(email="", password="testpass123")

        self.assertEqual(str(context.exception), "The Email field must be set")

    def test_create_user_with_empty_email_raises_error(self):
        """Test creating user with empty email raises ValueError"""
        with self.assertRaises(ValueError):
            User.objects.create_user(email=None, password="testpass123")

    def test_create_superuser(self):
        """Test creating a superuser"""
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpass123",
            name="Admin User"
        )

        self.assertEqual(user.email, "admin@example.com")
        self.assertEqual(user.name, "Admin User")
        self.assertTrue(user.check_password("adminpass123"))
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_create_superuser_with_is_staff_false_raises_error(self):
        """Test creating superuser with is_staff=False raises ValueError"""
        with self.assertRaises(ValueError) as context:
            User.objects.create_superuser(
                email="admin@example.com",
                password="adminpass123",
                is_staff=False
            )

        self.assertEqual(str(context.exception), "Superuser must have is_staff=True.")

    def test_create_superuser_with_is_superuser_false_raises_error(self):
        """Test creating superuser with is_superuser=False raises ValueError"""
        with self.assertRaises(ValueError) as context:
            User.objects.create_superuser(
                email="admin@example.com",
                password="adminpass123",
                is_superuser=False
            )

        self.assertEqual(str(context.exception), "Superuser must have is_superuser=True.")

    def test_user_string_representation(self):
        """Test user string representation"""
        user = User(email="test@example.com")
        self.assertEqual(str(user), "test@example.com")

    def test_get_full_name_with_name(self):
        """Test get_full_name method when name is provided"""
        user = User(email="test@example.com", name="John Doe")
        self.assertEqual(user.get_full_name(), "John Doe")

    def test_get_full_name_without_name(self):
        """Test get_full_name method when name is empty"""
        user = User(email="test@example.com", name="")
        self.assertEqual(user.get_full_name(), "test@example.com")

    def test_get_short_name_with_name(self):
        """Test get_short_name method when name is provided"""
        user = User(email="test@example.com", name="John Doe")
        self.assertEqual(user.get_short_name(), "John")

    def test_get_short_name_without_name(self):
        """Test get_short_name method when name is empty"""
        user = User(email="test@example.com", name="")
        self.assertEqual(user.get_short_name(), "test")

    def test_update_last_seen(self):
        """Test update_last_seen method"""
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )
        old_last_seen = user.last_seen

        # Update last seen
        user.update_last_seen()

        self.assertGreater(user.last_seen, old_last_seen)

    def test_user_email_uniqueness(self):
        """Test that user email must be unique"""
        User.objects.create_user(email="test@example.com", password="pass123")

        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="test@example.com", password="pass123")

    def test_email_normalization(self):
        """Test that email is normalized during user creation"""
        user = User.objects.create_user(
            email="Test@EXAMPLE.COM",
            password="testpass123"
        )
        self.assertEqual(user.email, "Test@example.com")

    def test_user_avatar_with_valid_extension(self):
        """Test user avatar with valid file extension"""
        # Create a simple image file
        image = Image.new('RGB', (100, 100), color='red')
        image_io = io.BytesIO()
        image.save(image_io, format='PNG')
        image_io.seek(0)

        avatar = SimpleUploadedFile(
            "test.png",
            image_io.getvalue(),
            content_type="image/png"
        )

        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            avatar=avatar
        )

        self.assertTrue(user.avatar.name.endswith('.png'))

    def test_user_meta_ordering(self):
        """Test that users are ordered by created_at descending"""
        user1 = User.objects.create_user(email="test1@example.com", password="pass")
        user2 = User.objects.create_user(email="test2@example.com", password="pass")

        users = list(User.objects.all())
        self.assertEqual(users[0], user2)  # Most recent first
        self.assertEqual(users[1], user1)


class UserGroupPermissionsTest(TestCase):
    """Test User model group-based permission methods"""

    def setUp(self):
        """Set up test groups and user"""
        self.admin_group = Group.objects.create(name="Admin")
        self.manager_group = Group.objects.create(name="Manager")
        self.member_group = Group.objects.create(name="Member")

        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )

    def test_has_group_true(self):
        """Test has_group method returns True when user is in group"""
        self.user.groups.add(self.admin_group)
        self.assertTrue(self.user.has_group("Admin"))

    def test_has_group_false(self):
        """Test has_group method returns False when user is not in group"""
        self.assertFalse(self.user.has_group("Admin"))

    def test_is_admin_with_admin_group(self):
        """Test is_admin method returns True when user is in Admin group"""
        self.user.groups.add(self.admin_group)
        self.assertTrue(self.user.is_admin())

    def test_is_admin_with_superuser(self):
        """Test is_admin method returns True when user is superuser"""
        self.user.is_superuser = True
        self.assertTrue(self.user.is_admin())

    def test_is_admin_false(self):
        """Test is_admin method returns False when user is not admin"""
        self.assertFalse(self.user.is_admin())

    def test_is_manager_with_manager_group(self):
        """Test is_manager method returns True when user is in Manager group"""
        self.user.groups.add(self.manager_group)
        self.assertTrue(self.user.is_manager())

    def test_is_manager_with_admin_group(self):
        """Test is_manager method returns True when user is admin"""
        self.user.groups.add(self.admin_group)
        self.assertTrue(self.user.is_manager())

    def test_is_manager_false(self):
        """Test is_manager method returns False when user is not manager"""
        self.assertFalse(self.user.is_manager())

    def test_is_member_with_member_group(self):
        """Test is_member method returns True when user is in Member group"""
        self.user.groups.add(self.member_group)
        self.assertTrue(self.user.is_member())

    def test_is_member_with_manager_group(self):
        """Test is_member method returns True when user is manager"""
        self.user.groups.add(self.manager_group)
        self.assertTrue(self.user.is_member())

    def test_is_member_with_admin_group(self):
        """Test is_member method returns True when user is admin"""
        self.user.groups.add(self.admin_group)
        self.assertTrue(self.user.is_member())

    def test_is_member_false(self):
        """Test is_member method returns False when user has no relevant groups"""
        self.assertFalse(self.user.is_member())


class UserProfileModelTest(TestCase):
    """Test UserProfile model functionality"""

    def setUp(self):
        """Set up test user"""
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )

    def test_user_profile_creation(self):
        """Test that UserProfile can be created"""
        profile = UserProfile.objects.create(
            user=self.user,
            bio="Test bio",
            location="Test City",
            website="https://example.com",
            phone="123-456-7890",
            timezone="America/New_York",
            language="en",
            receive_notifications=True,
            receive_marketing_emails=False
        )

        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.bio, "Test bio")
        self.assertEqual(profile.location, "Test City")
        self.assertEqual(profile.website, "https://example.com")
        self.assertEqual(profile.phone, "123-456-7890")
        self.assertEqual(profile.timezone, "America/New_York")
        self.assertEqual(profile.language, "en")
        self.assertTrue(profile.receive_notifications)
        self.assertFalse(profile.receive_marketing_emails)
        self.assertIsNotNone(profile.created_at)
        self.assertIsNotNone(profile.updated_at)

    def test_user_profile_string_representation(self):
        """Test UserProfile string representation"""
        profile = UserProfile.objects.create(user=self.user)
        self.assertEqual(str(profile), f"{self.user.email} Profile")

    def test_user_profile_defaults(self):
        """Test UserProfile default values"""
        profile = UserProfile.objects.create(user=self.user)

        self.assertEqual(profile.bio, "")
        self.assertEqual(profile.location, "")
        self.assertEqual(profile.website, "")
        self.assertEqual(profile.phone, "")
        self.assertEqual(profile.timezone, "UTC")
        self.assertEqual(profile.language, "en")
        self.assertTrue(profile.receive_notifications)
        self.assertFalse(profile.receive_marketing_emails)

    def test_user_profile_one_to_one_relationship(self):
        """Test that UserProfile has one-to-one relationship with User"""
        profile = UserProfile.objects.create(user=self.user)

        # Test forward relationship
        self.assertEqual(profile.user, self.user)

        # Test reverse relationship
        self.assertEqual(self.user.profile, profile)

    def test_user_profile_cascade_delete(self):
        """Test that UserProfile is deleted when User is deleted"""
        profile = UserProfile.objects.create(user=self.user)
        profile_id = profile.id

        # Delete user
        self.user.delete()

        # Check that profile is also deleted
        self.assertFalse(UserProfile.objects.filter(id=profile_id).exists())

    def test_user_profile_verbose_names(self):
        """Test UserProfile model verbose names"""
        self.assertEqual(UserProfile._meta.verbose_name, "User Profile")
        self.assertEqual(UserProfile._meta.verbose_name_plural, "User Profiles")


@pytest.mark.django_db
class TestUserModelWithPytest:
    """Additional pytest-style tests for User model"""

    def test_user_creation_with_pytest(self, user):
        """Test user creation using pytest fixture"""
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.is_active is True
        assert user.is_staff is False

    def test_user_manager_email_normalization(self):
        """Test email normalization in custom user manager"""
        user = User.objects.create_user(
            email="Test@EXAMPLE.COM",
            password="testpass123"
        )
        assert user.email == "Test@example.com"

    def test_superuser_creation_with_defaults(self):
        """Test superuser creation with default extra_fields"""
        user = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpass123"
        )
        assert user.is_staff is True
        assert user.is_superuser is True
        assert user.is_active is True

    def test_user_timestamp_fields(self):
        """Test that timestamp fields are set correctly"""
        user = User.objects.create_user(
            email="test@example.com",
            password="testpass123"
        )

        assert user.created_at is not None
        assert user.updated_at is not None
        assert user.last_seen is not None

        # Check that created_at and updated_at are close to current time
        now = timezone.now()
        assert abs((now - user.created_at).total_seconds()) < 60
        assert abs((now - user.updated_at).total_seconds()) < 60

    def test_user_required_fields(self):
        """Test that REQUIRED_FIELDS is empty (only email is required)"""
        assert User.REQUIRED_FIELDS == []
        assert User.USERNAME_FIELD == "email"

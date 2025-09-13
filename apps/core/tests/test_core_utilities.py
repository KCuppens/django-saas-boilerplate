"""Comprehensive tests for core utilities - mixins, permissions, validators."""

import tempfile
from datetime import timedelta
from unittest.mock import MagicMock, Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils import timezone

from rest_framework import permissions
from rest_framework.test import APIRequestFactory

from apps.core.mixins import (
    ActiveManager,
    AllObjectsManager,
    FullTrackingMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UserTrackingMixin,
)
from apps.core.permissions import (
    HasGroup,
    IsAdminOrReadOnly,
    IsManagerOrAdmin,
    IsMemberOrAbove,
    IsOwnerOrAdmin,
    IsOwnerOrPublic,
)
from apps.core.utils import (
    create_slug,
    format_file_size,
    generate_hash,
    generate_secure_token,
    generate_short_uuid,
    generate_uuid,
    get_client_ip,
    get_user_agent,
    mask_email,
    safe_get_dict_value,
    send_notification_email,
    time_since_creation,
    truncate_string,
    validate_json_structure,
)
from apps.core.validators import (
    FileValidator,
    validate_alphanumeric,
    validate_file_size,
    validate_image_dimensions,
    validate_no_special_chars,
    validate_phone_number,
    validate_slug_format,
)

User = get_user_model()


# Test models to verify mixins
class TestTimestampModel(TimestampMixin):
    """Test model using TimestampMixin."""

    class Meta:
        """Meta configuration for test model."""

        app_label = "core"


class TestUserTrackingModel(UserTrackingMixin):
    """Test model using UserTrackingMixin."""

    class Meta:
        """Meta configuration for test model."""

        app_label = "core"


class TestFullTrackingModel(FullTrackingMixin):
    """Test model using FullTrackingMixin."""

    class Meta:
        """Meta configuration for test model."""

        app_label = "core"


class TestSoftDeleteModel(SoftDeleteMixin):
    """Test model using SoftDeleteMixin."""

    objects = ActiveManager()
    all_objects = AllObjectsManager()

    class Meta:
        """Meta configuration for test model."""

        app_label = "core"


class CoreMixinsTestCase(TestCase):
    """Test core model mixins."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

    def test_timestamp_mixin_fields(self):
        """Test TimestampMixin provides correct fields."""
        model = TestTimestampModel()

        # Check that timestamp fields exist
        self.assertTrue(hasattr(model, "created_at"))
        self.assertTrue(hasattr(model, "updated_at"))

        # Check field types
        self.assertEqual(model._meta.get_field("created_at").auto_now_add, True)
        self.assertEqual(model._meta.get_field("updated_at").auto_now, True)

    def test_user_tracking_mixin_fields(self):
        """Test UserTrackingMixin provides correct fields."""
        model = TestUserTrackingModel()

        # Check that user tracking fields exist
        self.assertTrue(hasattr(model, "created_by"))
        self.assertTrue(hasattr(model, "updated_by"))

        # Check field configuration
        created_by_field = model._meta.get_field("created_by")
        self.assertEqual(created_by_field.related_model, User)
        self.assertTrue(created_by_field.null)

    def test_full_tracking_mixin_inherits_both(self):
        """Test FullTrackingMixin inherits from both timestamp and user tracking."""
        model = TestFullTrackingModel()

        # Should have all fields from both mixins
        self.assertTrue(hasattr(model, "created_at"))
        self.assertTrue(hasattr(model, "updated_at"))
        self.assertTrue(hasattr(model, "created_by"))
        self.assertTrue(hasattr(model, "updated_by"))

    def test_soft_delete_mixin_fields(self):
        """Test SoftDeleteMixin provides correct fields."""
        model = TestSoftDeleteModel()

        # Check that soft delete fields exist
        self.assertTrue(hasattr(model, "is_deleted"))
        self.assertTrue(hasattr(model, "deleted_at"))
        self.assertTrue(hasattr(model, "deleted_by"))

        # Check default values
        self.assertFalse(model.is_deleted)
        self.assertIsNone(model.deleted_at)
        self.assertIsNone(model.deleted_by)

    def test_soft_delete_functionality(self):
        """Test soft delete and restore functionality."""
        # This test would need actual database tables, so we'll test the logic
        model = TestSoftDeleteModel()
        model.deleted_by = self.user

        # Mock the save method
        model.save = Mock()

        # Test soft delete
        model.delete(soft=True)
        self.assertTrue(model.is_deleted)
        self.assertIsNotNone(model.deleted_at)
        model.save.assert_called_once()

        # Test restore
        model.save.reset_mock()
        model.restore()
        self.assertFalse(model.is_deleted)
        self.assertIsNone(model.deleted_at)
        self.assertIsNone(model.deleted_by)
        model.save.assert_called_once()

    def test_active_manager_filters_deleted(self):
        """Test ActiveManager filters out soft-deleted records."""
        manager = ActiveManager()

        # Mock the parent get_queryset method
        mock_queryset = Mock()
        mock_queryset.filter.return_value = "filtered_queryset"

        with patch(
            "django.db.models.Manager.get_queryset", return_value=mock_queryset
        ) as mock_super:
            manager.get_queryset()

            # Should call parent get_queryset and then filter
            mock_super.assert_called_once()
            mock_queryset.filter.assert_called_once_with(is_deleted=False)

    def test_all_objects_manager_includes_all(self):
        """Test AllObjectsManager includes all records."""
        manager = AllObjectsManager()

        # Mock the parent get_queryset
        with patch(
            "django.db.models.Manager.get_queryset", return_value="all_records"
        ) as mock_super:
            result = manager.get_queryset()

            # Should return all records without filtering
            self.assertEqual(result, "all_records")
            mock_super.assert_called_once()


class CorePermissionsTestCase(TestCase):
    """Test core permission classes."""

    def setUp(self):
        """Set up test data."""
        self.factory = APIRequestFactory()

        # Create users
        self.regular_user = User.objects.create_user(
            email="regular@example.com", password="testpass123", name="Regular User"
        )

        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="adminpass123",
            name="Admin User",
            is_staff=True,
            is_superuser=True,
        )

        # Create groups
        self.member_group = Group.objects.create(name="Member")
        self.manager_group = Group.objects.create(name="Manager")
        self.admin_group = Group.objects.create(name="Admin")

        # Add users to groups
        self.regular_user.groups.add(self.member_group)
        self.admin_user.groups.add(self.admin_group)

    def test_has_group_permission_factory(self):
        """Test HasGroup permission factory."""
        MemberPermission = HasGroup("Member")
        AdminPermission = HasGroup("Admin")

        permission_member = MemberPermission()
        permission_admin = AdminPermission()

        # Create requests
        member_request = self.factory.get("/")
        member_request.user = self.regular_user

        admin_request = self.factory.get("/")
        admin_request.user = self.admin_user

        # Test member permission
        self.assertTrue(permission_member.has_permission(member_request, None))
        self.assertFalse(permission_admin.has_permission(member_request, None))

        # Test anonymous user
        anon_request = self.factory.get("/")
        anon_request.user = None
        self.assertFalse(permission_member.has_permission(anon_request, None))

    def test_is_admin_or_read_only_permission(self):
        """Test IsAdminOrReadOnly permission."""
        permission = IsAdminOrReadOnly()

        # Test read permission for regular user
        read_request = self.factory.get("/")
        read_request.user = self.regular_user
        self.assertTrue(permission.has_permission(read_request, None))

        # Test write permission for regular user
        write_request = self.factory.post("/")
        write_request.user = self.regular_user

        with patch.object(self.regular_user, "is_admin", return_value=False):
            self.assertFalse(permission.has_permission(write_request, None))

        # Test write permission for admin
        admin_write_request = self.factory.post("/")
        admin_write_request.user = self.admin_user

        with patch.object(self.admin_user, "is_admin", return_value=True):
            self.assertTrue(permission.has_permission(admin_write_request, None))

    def test_is_owner_or_admin_permission(self):
        """Test IsOwnerOrAdmin permission."""
        permission = IsOwnerOrAdmin()

        # Create mock objects
        owned_obj = Mock()
        owned_obj.user = self.regular_user

        other_obj = Mock()
        other_obj.user = self.admin_user

        user_obj = self.regular_user

        # Test owner access
        request = self.factory.get("/")
        request.user = self.regular_user

        self.assertTrue(permission.has_object_permission(request, None, owned_obj))
        self.assertFalse(permission.has_object_permission(request, None, other_obj))
        self.assertTrue(permission.has_object_permission(request, None, user_obj))

        # Test admin access
        admin_request = self.factory.get("/")
        admin_request.user = self.admin_user

        with patch.object(self.admin_user, "is_admin", return_value=True):
            self.assertTrue(
                permission.has_object_permission(admin_request, None, owned_obj)
            )
            self.assertTrue(
                permission.has_object_permission(admin_request, None, other_obj)
            )

    def test_is_manager_or_admin_permission(self):
        """Test IsManagerOrAdmin permission."""
        permission = IsManagerOrAdmin()

        request = self.factory.get("/")
        request.user = self.regular_user

        # Test regular user
        with patch.object(self.regular_user, "is_manager", return_value=False):
            self.assertFalse(permission.has_permission(request, None))

        # Test manager
        with patch.object(self.regular_user, "is_manager", return_value=True):
            self.assertTrue(permission.has_permission(request, None))

    def test_is_member_or_above_permission(self):
        """Test IsMemberOrAbove permission."""
        permission = IsMemberOrAbove()

        request = self.factory.get("/")
        request.user = self.regular_user

        # Test member
        with patch.object(self.regular_user, "is_member", return_value=True):
            self.assertTrue(permission.has_permission(request, None))

        # Test non-member
        with patch.object(self.regular_user, "is_member", return_value=False):
            self.assertFalse(permission.has_permission(request, None))

    def test_is_owner_or_public_permission(self):
        """Test IsOwnerOrPublic permission."""
        permission = IsOwnerOrPublic()

        # Create mock objects
        private_obj = Mock()
        private_obj.created_by = self.regular_user
        private_obj.is_public = False

        public_obj = Mock()
        public_obj.created_by = self.admin_user
        public_obj.is_public = True

        # Test owner access to private object
        owner_request = self.factory.get("/")
        owner_request.user = self.regular_user

        self.assertTrue(
            permission.has_object_permission(owner_request, None, private_obj)
        )

        # Test other user access to public object (read-only)
        other_request = self.factory.get("/")
        other_request.user = self.admin_user
        other_request.method = "GET"

        self.assertTrue(
            permission.has_object_permission(other_request, None, public_obj)
        )

        # Test non-admin user access to private object owned by different user
        non_admin_request = self.factory.get("/")
        non_admin_request.user = self.admin_user
        non_admin_request.method = "GET"

        # Remove admin privileges temporarily to test non-admin access
        with patch.object(self.admin_user, "is_admin", return_value=False):
            self.assertFalse(
                permission.has_object_permission(non_admin_request, None, private_obj)
            )


class CoreValidatorsTestCase(TestCase):
    """Test core validator functions."""

    def test_validate_phone_number_valid(self):
        """Test phone number validation with valid numbers."""
        valid_numbers = [
            "+1234567890",
            "1234567890",
            "+12345678901",
            "123456789012345",  # 15 digits
        ]

        for number in valid_numbers:
            with self.subTest(number=number):
                # Should not raise ValidationError
                validate_phone_number(number)

    def test_validate_phone_number_invalid(self):
        """Test phone number validation with invalid numbers."""
        invalid_numbers = [
            "123",  # Too short
            "12345678901234567890",  # Too long
            "+1-234-567-890",  # Contains hyphens
            "abc1234567890",  # Contains letters
            "",  # Empty
        ]

        for number in invalid_numbers:
            with self.subTest(number=number), self.assertRaises(ValidationError):
                validate_phone_number(number)

    def test_validate_no_special_chars_valid(self):
        """Test no special chars validation with valid input."""
        valid_inputs = [
            "Hello World",
            "123 ABC",
            "Test123",
            "   ",  # Just spaces
            "a1b2c3",
        ]

        for input_val in valid_inputs:
            with self.subTest(input=input_val):
                validate_no_special_chars(input_val)

    def test_validate_no_special_chars_invalid(self):
        """Test no special chars validation with invalid input."""
        invalid_inputs = [
            "Hello@World",
            "Test!123",
            "user@domain.com",
            "special#chars",
            "dots.not.allowed",
        ]

        for input_val in invalid_inputs:
            with self.subTest(input=input_val), self.assertRaises(ValidationError):
                validate_no_special_chars(input_val)

    def test_validate_alphanumeric_valid(self):
        """Test alphanumeric validation with valid input."""
        valid_inputs = ["abc123", "ABC", "123", "Test123", ""]

        for input_val in valid_inputs:
            with self.subTest(input=input_val):
                validate_alphanumeric(input_val)

    def test_validate_alphanumeric_invalid(self):
        """Test alphanumeric validation with invalid input."""
        invalid_inputs = [
            "hello world",  # Contains space
            "test@123",
            "abc-def",
            "test_123",
        ]

        for input_val in invalid_inputs:
            with self.subTest(input=input_val), self.assertRaises(ValidationError):
                validate_alphanumeric(input_val)

    def test_validate_slug_format_valid(self):
        """Test slug format validation with valid input."""
        valid_slugs = ["hello-world", "test123", "my-slug-123", "simple", ""]

        for slug in valid_slugs:
            with self.subTest(slug=slug):
                validate_slug_format(slug)

    def test_validate_slug_format_invalid(self):
        """Test slug format validation with invalid input."""
        invalid_slugs = [
            "Hello-World",  # Uppercase
            "hello_world",  # Underscore
            "hello world",  # Space
            "hello@world",  # Special char
        ]

        for slug in invalid_slugs:
            with self.subTest(slug=slug), self.assertRaises(ValidationError):
                validate_slug_format(slug)

    def test_validate_file_size_valid(self):
        """Test file size validation with valid files."""
        # Create mock file with small size
        mock_file = Mock()
        mock_file.size = 1024 * 1024  # 1MB

        # Should not raise for 5MB limit
        validate_file_size(mock_file, max_size_mb=5)

    def test_validate_file_size_invalid(self):
        """Test file size validation with oversized files."""
        # Create mock file with large size
        mock_file = Mock()
        mock_file.size = 10 * 1024 * 1024  # 10MB

        # Should raise for 5MB limit
        with self.assertRaises(ValidationError):
            validate_file_size(mock_file, max_size_mb=5)

    @patch("PIL.Image.open")
    def test_validate_image_dimensions_valid(self, mock_image_open):
        """Test image dimension validation with valid images."""
        # Mock PIL Image
        mock_img = Mock()
        mock_img.size = (1024, 768)  # Within limits
        mock_image_open.return_value.__enter__.return_value = mock_img

        mock_file = Mock()

        # Should not raise for 1920x1080 limit
        validate_image_dimensions(mock_file)

    @patch("PIL.Image.open")
    def test_validate_image_dimensions_invalid(self, mock_image_open):
        """Test image dimension validation with oversized images."""
        # Mock PIL Image
        mock_img = Mock()
        mock_img.size = (2560, 1440)  # Exceeds limits
        mock_image_open.return_value.__enter__.return_value = mock_img

        mock_file = Mock()

        # Should raise for 1920x1080 limit
        with self.assertRaises(ValidationError):
            validate_image_dimensions(mock_file)

    def test_file_validator_class(self):
        """Test FileValidator class functionality."""
        # Test with size and extension constraints
        validator = FileValidator(
            max_size_mb=5,
            allowed_extensions=["pdf", "jpg"],
            allowed_content_types=["application/pdf", "image/jpeg"],
        )

        # Create mock valid file
        valid_file = Mock()
        valid_file.size = 1024 * 1024  # 1MB
        valid_file.name = "test.pdf"
        valid_file.content_type = "application/pdf"

        # Should not raise
        validator(valid_file)

        # Test with invalid extension
        invalid_file = Mock()
        invalid_file.size = 1024 * 1024  # 1MB
        invalid_file.name = "test.txt"
        invalid_file.content_type = "text/plain"

        with self.assertRaises(ValidationError):
            validator(invalid_file)


class CoreUtilsTestCase(TestCase):
    """Test core utility functions."""

    def test_generate_uuid(self):
        """Test UUID generation."""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()

        # Should be strings
        self.assertIsInstance(uuid1, str)
        self.assertIsInstance(uuid2, str)

        # Should be different
        self.assertNotEqual(uuid1, uuid2)

        # Should be valid UUID format
        self.assertEqual(len(uuid1), 36)  # Standard UUID length
        self.assertIn("-", uuid1)

    def test_generate_short_uuid(self):
        """Test short UUID generation."""
        short_uuid = generate_short_uuid(8)

        self.assertIsInstance(short_uuid, str)
        self.assertEqual(len(short_uuid), 8)
        self.assertNotIn("-", short_uuid)  # No hyphens in short UUID

    def test_generate_secure_token(self):
        """Test secure token generation."""
        token1 = generate_secure_token(32)
        token2 = generate_secure_token(32)

        self.assertIsInstance(token1, str)
        self.assertIsInstance(token2, str)
        self.assertNotEqual(token1, token2)

    def test_generate_hash(self):
        """Test hash generation."""
        data = "test data"

        # Test SHA256 (default)
        hash_sha256 = generate_hash(data)
        self.assertEqual(len(hash_sha256), 64)  # SHA256 hex length

        # Test MD5
        hash_md5 = generate_hash(data, algorithm="md5")
        self.assertEqual(len(hash_md5), 32)  # MD5 hex length

        # Same input should produce same hash
        hash_sha256_2 = generate_hash(data)
        self.assertEqual(hash_sha256, hash_sha256_2)

    def test_create_slug(self):
        """Test slug creation."""
        test_cases = [
            ("Hello World", "hello-world"),
            ("Test@123", "test123"),
            ("  Spaced  ", "spaced"),
            (
                "Very Long Title That Should Be Truncated",
                "very-long-title-that-should-be-truncated",
            ),
        ]

        for input_text, expected_slug in test_cases:
            with self.subTest(input=input_text):
                slug = create_slug(input_text, max_length=50)
                self.assertEqual(slug, expected_slug)

    def test_create_slug_with_truncation(self):
        """Test slug creation with length limit."""
        long_text = "This is a very long title that needs to be truncated"
        slug = create_slug(long_text, max_length=20)

        self.assertLessEqual(len(slug), 20)
        self.assertFalse(slug.endswith("-"))  # Should not end with hyphen

    def test_safe_get_dict_value(self):
        """Test safe dictionary value retrieval."""
        test_dict = {"key1": "value1", "key2": None}

        # Test existing key
        self.assertEqual(safe_get_dict_value(test_dict, "key1"), "value1")

        # Test missing key with default
        self.assertEqual(safe_get_dict_value(test_dict, "key3", "default"), "default")

        # Test None value
        self.assertIsNone(safe_get_dict_value(test_dict, "key2"))

        # Test with None dictionary
        self.assertEqual(safe_get_dict_value(None, "key1", "default"), "default")

    def test_truncate_string(self):
        """Test string truncation."""
        long_text = "This is a very long string that needs to be truncated"

        # Test normal truncation
        truncated = truncate_string(long_text, max_length=20)
        self.assertEqual(len(truncated), 20)
        self.assertTrue(truncated.endswith("..."))

        # Test string shorter than limit
        short_text = "Short"
        truncated_short = truncate_string(short_text, max_length=20)
        self.assertEqual(truncated_short, short_text)

        # Test custom suffix
        truncated_custom = truncate_string(long_text, max_length=20, suffix="...")
        self.assertTrue(truncated_custom.endswith("..."))

    def test_format_file_size(self):
        """Test file size formatting."""
        test_cases = [
            (0, "0 B"),
            (512, "512.0 B"),
            (1024, "1.0 KB"),
            (1024 * 1024, "1.0 MB"),
            (1024 * 1024 * 1024, "1.0 GB"),
            (1536, "1.5 KB"),  # 1.5 KB
        ]

        for size_bytes, expected in test_cases:
            with self.subTest(size=size_bytes):
                result = format_file_size(size_bytes)
                self.assertEqual(result, expected)

    def test_get_client_ip(self):
        """Test client IP extraction."""
        factory = RequestFactory()

        # Test with X-Forwarded-For
        request = factory.get("/")
        request.headers = {"x-forwarded-for": "192.168.1.1, 10.0.0.1"}
        ip = get_client_ip(request)
        self.assertEqual(ip, "192.168.1.1")  # Should get first IP

        # Test with REMOTE_ADDR
        request2 = factory.get("/")
        request2.headers = {}
        request2.META = {"REMOTE_ADDR": "127.0.0.1"}
        ip2 = get_client_ip(request2)
        self.assertEqual(ip2, "127.0.0.1")

    def test_get_user_agent(self):
        """Test user agent extraction."""
        factory = RequestFactory()

        # Test with user agent
        request = factory.get("/")
        request.headers = {"user-agent": "Mozilla/5.0 Test Browser"}
        user_agent = get_user_agent(request)
        self.assertEqual(user_agent, "Mozilla/5.0 Test Browser")

        # Test without user agent
        request2 = factory.get("/")
        request2.headers = {}
        user_agent2 = get_user_agent(request2)
        self.assertEqual(user_agent2, "")

    def test_time_since_creation(self):
        """Test time since creation formatting."""
        now = timezone.now()

        # Test minutes ago
        minutes_ago = now - timedelta(minutes=30)
        result = time_since_creation(minutes_ago)
        self.assertEqual(result, "30 minutes ago")

        # Test hours ago
        hours_ago = now - timedelta(hours=5)
        result = time_since_creation(hours_ago)
        self.assertEqual(result, "5 hours ago")

        # Test days ago
        days_ago = now - timedelta(days=3)
        result = time_since_creation(days_ago)
        self.assertEqual(result, "3 days ago")

        # Test just now
        just_now = now - timedelta(seconds=30)
        result = time_since_creation(just_now)
        self.assertEqual(result, "Just now")

    @patch("apps.core.utils.send_mail")
    def test_send_notification_email_success(self, mock_send_mail):
        """Test successful notification email sending."""
        mock_send_mail.return_value = True

        result = send_notification_email(
            subject="Test Subject",
            message="Test Message",
            recipient_list=["test@example.com"],
        )

        self.assertTrue(result)
        mock_send_mail.assert_called_once()

    @patch("apps.core.utils.send_mail")
    def test_send_notification_email_failure(self, mock_send_mail):
        """Test notification email sending failure."""
        mock_send_mail.side_effect = Exception("SMTP Error")

        # With fail_silently=True
        result = send_notification_email(
            subject="Test Subject",
            message="Test Message",
            recipient_list=["test@example.com"],
            fail_silently=True,
        )

        self.assertFalse(result)

        # With fail_silently=False
        with self.assertRaisesRegex(Exception, "SMTP Error"):
            send_notification_email(
                subject="Test Subject",
                message="Test Message",
                recipient_list=["test@example.com"],
                fail_silently=False,
            )

    def test_mask_email(self):
        """Test email masking for privacy."""
        test_cases = [
            ("test@example.com", "t**t@example.com"),
            ("a@example.com", "a@example.com"),  # Single char
            ("ab@example.com", "a*@example.com"),  # Two chars
            ("user@domain.co.uk", "u**r@domain.co.uk"),
            ("invalid-email", "invalid-email"),  # No @ symbol
        ]

        for email, expected in test_cases:
            with self.subTest(email=email):
                result = mask_email(email)
                self.assertEqual(result, expected)

    def test_validate_json_structure(self):
        """Test JSON structure validation."""
        # Test valid structure
        valid_data = {"name": "John", "email": "john@example.com", "age": 30}
        required_fields = ["name", "email"]

        errors = validate_json_structure(valid_data, required_fields)
        self.assertEqual(len(errors), 0)

        # Test missing fields
        invalid_data = {"name": "John"}
        errors = validate_json_structure(invalid_data, required_fields)
        self.assertEqual(len(errors), 1)
        self.assertIn("email", errors)
        self.assertIn("required", errors["email"])


class CoreIntegrationTestCase(TestCase):
    """Integration tests for core utilities working together."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

    def test_complete_permission_workflow(self):
        """Test complete permission checking workflow."""
        # Create a mock object with user tracking
        mock_obj = Mock()
        mock_obj.created_by = self.user
        mock_obj.is_public = False

        # Ensure the mock doesn't have user attribute to force checking created_by
        del mock_obj.user

        # Test owner permission
        owner_permission = IsOwnerOrAdmin()
        factory = APIRequestFactory()
        request = factory.get("/")
        request.user = self.user

        # Owner should have access
        self.assertTrue(owner_permission.has_object_permission(request, None, mock_obj))

        # Other user should not have access
        other_user = User.objects.create_user(
            email="other@example.com", password="otherpass123", name="Other User"
        )
        request.user = other_user
        self.assertFalse(
            owner_permission.has_object_permission(request, None, mock_obj)
        )

    def test_validation_chain_workflow(self):
        """Test chaining multiple validators."""
        # Create a composite validator using FileValidator
        validator = FileValidator(
            max_size_mb=5,
            allowed_extensions=["pdf"],
            allowed_content_types=["application/pdf"],
        )

        # Test valid file
        valid_file = Mock()
        valid_file.size = 1024 * 1024  # 1MB
        valid_file.name = "document.pdf"
        valid_file.content_type = "application/pdf"

        # Should pass all validations
        validator(valid_file)

        # Test file that fails multiple validations
        invalid_file = Mock()
        invalid_file.size = 10 * 1024 * 1024  # 10MB - too large
        invalid_file.name = "document.txt"  # Wrong extension
        invalid_file.content_type = "text/plain"  # Wrong content type

        # Should fail on first validation (size)
        with self.assertRaises(ValidationError):
            validator(invalid_file)

    def test_utility_functions_integration(self):
        """Test utility functions working together."""
        # Generate a secure token and create a slug from it
        token = generate_secure_token(16)
        slug = create_slug(f"document-{token}", max_length=30)

        # Should create valid slug
        self.assertIsInstance(slug, str)
        self.assertLessEqual(len(slug), 30)

        # Test with email masking and validation
        email = "user@example.com"
        masked = mask_email(email)

        # Validate that masking worked
        self.assertNotEqual(email, masked)
        self.assertIn("@", masked)

        # Test JSON validation with utility functions
        data = {"email": email, "slug": slug, "token": token}

        errors = validate_json_structure(data, ["email", "slug"])
        self.assertEqual(len(errors), 0)

    def test_hash_and_security_workflow(self):
        """Test security-related utility functions."""
        # Generate secure data
        uuid_val = generate_uuid()
        short_uuid = generate_short_uuid(8)
        token = generate_secure_token(32)

        # Create hashes
        hash1 = generate_hash(uuid_val)
        hash2 = generate_hash(short_uuid)

        # All should be unique
        unique_values = {uuid_val, short_uuid, token, hash1, hash2}
        self.assertEqual(len(unique_values), 5)

        # Hashes should be deterministic
        hash1_repeat = generate_hash(uuid_val)
        self.assertEqual(hash1, hash1_repeat)

"""Test cases for core application functionality."""

import hashlib
import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory, TestCase
from django.utils import timezone

from .enums import (
    EmailStatus,
    FileType,
    NotificationType,
    Priority,
    Status,
    TaskStatus,
    UserRole,
)
from .permissions import HasGroup, IsAdminOrReadOnly, IsOwnerOrAdmin
from .utils import (
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

User = get_user_model()


class EnumsTestCase(TestCase):
    """Test enum classes."""

    def test_user_role_choices(self):
        """Test UserRole enum values."""
        self.assertEqual(UserRole.ADMIN, "admin")
        self.assertEqual(UserRole.MANAGER, "manager")
        self.assertEqual(UserRole.MEMBER, "member")
        self.assertEqual(UserRole.READ_ONLY, "readonly")

    def test_email_status_choices(self):
        """Test EmailStatus enum values."""
        self.assertEqual(EmailStatus.PENDING, "pending")
        self.assertEqual(EmailStatus.SENT, "sent")
        self.assertEqual(EmailStatus.FAILED, "failed")
        self.assertEqual(EmailStatus.BOUNCED, "bounced")

    def test_file_type_choices(self):
        """Test FileType enum values."""
        self.assertEqual(FileType.IMAGE, "image")
        self.assertEqual(FileType.DOCUMENT, "document")
        self.assertEqual(FileType.VIDEO, "video")

    def test_notification_type_choices(self):
        """Test NotificationType enum values."""
        self.assertEqual(NotificationType.INFO, "info")
        self.assertEqual(NotificationType.SUCCESS, "success")
        self.assertEqual(NotificationType.WARNING, "warning")
        self.assertEqual(NotificationType.ERROR, "error")

    def test_priority_choices(self):
        """Test Priority enum values."""
        self.assertEqual(Priority.LOW, "low")
        self.assertEqual(Priority.MEDIUM, "medium")
        self.assertEqual(Priority.HIGH, "high")
        self.assertEqual(Priority.URGENT, "urgent")

    def test_status_choices(self):
        """Test Status enum values."""
        self.assertEqual(Status.DRAFT, "draft")
        self.assertEqual(Status.ACTIVE, "active")
        self.assertEqual(Status.INACTIVE, "inactive")

    def test_task_status_choices(self):
        """Test TaskStatus enum values."""
        self.assertEqual(TaskStatus.PENDING, "pending")
        self.assertEqual(TaskStatus.IN_PROGRESS, "in_progress")
        self.assertEqual(TaskStatus.COMPLETED, "completed")


class PermissionsTestCase(TestCase):
    """Test permission classes."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com", name="Admin User", password="adminpass123"
        )

    def test_has_group_permission_authenticated_user_in_group(self):
        """Test HasGroup permission with user in group."""
        group = Group.objects.create(name="test_group")
        self.user.groups.add(group)

        permission_class = HasGroup("test_group")
        permission = permission_class()
        request = Mock()
        request.user = self.user

        self.assertTrue(permission.has_permission(request, None))

    def test_has_group_permission_authenticated_user_not_in_group(self):
        """Test HasGroup permission with user not in group."""
        permission_class = HasGroup("test_group")
        permission = permission_class()
        request = Mock()
        request.user = self.user

        self.assertFalse(permission.has_permission(request, None))

    def test_has_group_permission_unauthenticated_user(self):
        """Test HasGroup permission with unauthenticated user."""
        permission_class = HasGroup("test_group")
        permission = permission_class()
        request = Mock()
        request.user = Mock()
        request.user.is_authenticated = False

        self.assertFalse(permission.has_permission(request, None))

    def test_is_admin_or_read_only_admin_write(self):
        """Test IsAdminOrReadOnly permission for admin write access."""
        permission = IsAdminOrReadOnly()
        request = Mock()
        request.user = self.admin_user
        request.method = "POST"

        # Mock the is_admin method
        self.admin_user.is_admin = Mock(return_value=True)

        self.assertTrue(permission.has_permission(request, None))

    def test_is_admin_or_read_only_regular_user_read(self):
        """Test IsAdminOrReadOnly permission for regular user read access."""
        permission = IsAdminOrReadOnly()
        request = Mock()
        request.user = self.user
        request.method = "GET"

        self.assertTrue(permission.has_permission(request, None))

    def test_is_admin_or_read_only_regular_user_write(self):
        """Test IsAdminOrReadOnly permission for regular user write access."""
        permission = IsAdminOrReadOnly()
        request = Mock()
        request.user = self.user
        request.method = "POST"

        # Mock the is_admin method
        self.user.is_admin = Mock(return_value=False)

        self.assertFalse(permission.has_permission(request, None))

    def test_is_owner_or_admin_owner_access(self):
        """Test IsOwnerOrAdmin permission for owner access."""
        permission = IsOwnerOrAdmin()
        request = Mock()
        request.user = self.user

        obj = Mock()
        obj.user = self.user

        self.assertTrue(permission.has_object_permission(request, None, obj))

    def test_is_owner_or_admin_admin_access(self):
        """Test IsOwnerOrAdmin permission for admin access."""
        permission = IsOwnerOrAdmin()
        request = Mock()
        request.user = self.admin_user

        # Mock the is_admin method
        self.admin_user.is_admin = Mock(return_value=True)

        obj = Mock()
        obj.user = self.user

        self.assertTrue(permission.has_object_permission(request, None, obj))


class UtilsTestCase(TestCase):
    """Test utility functions."""

    def test_generate_uuid(self):
        """Test UUID generation."""
        generated_uuid = generate_uuid()
        self.assertIsInstance(generated_uuid, str)
        # Validate it's a valid UUID
        uuid.UUID(generated_uuid)

    def test_generate_short_uuid(self):
        """Test short UUID generation."""
        short_uuid = generate_short_uuid()
        self.assertEqual(len(short_uuid), 8)

        custom_length = generate_short_uuid(12)
        self.assertEqual(len(custom_length), 12)

    def test_generate_secure_token(self):
        """Test secure token generation."""
        token = generate_secure_token()
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 30)

        custom_token = generate_secure_token(16)
        self.assertIsInstance(custom_token, str)

    def test_generate_hash(self):
        """Test hash generation."""
        data = "test data"
        hash_result = generate_hash(data)

        # Verify it's a valid SHA256 hash
        expected_hash = hashlib.sha256(data.encode()).hexdigest()
        self.assertEqual(hash_result, expected_hash)

        # Test different algorithm
        md5_hash = generate_hash(data, "md5")
        expected_md5 = hashlib.md5(data.encode(), usedforsecurity=False).hexdigest()
        self.assertEqual(md5_hash, expected_md5)

    def test_create_slug(self):
        """Test slug creation."""
        slug = create_slug("Hello World Test")
        self.assertEqual(slug, "hello-world-test")

        # Test max length
        long_text = "This is a very long text that should be truncated"
        short_slug = create_slug(long_text, 20)
        self.assertLessEqual(len(short_slug), 20)

    def test_safe_get_dict_value(self):
        """Test safe dictionary value retrieval."""
        test_dict = {"key1": "value1", "key2": None}

        self.assertEqual(safe_get_dict_value(test_dict, "key1"), "value1")
        self.assertEqual(safe_get_dict_value(test_dict, "key2"), None)
        self.assertEqual(
            safe_get_dict_value(test_dict, "missing", "default"), "default"
        )

        # Test with None dictionary
        self.assertEqual(safe_get_dict_value(None, "key", "default"), "default")

    def test_truncate_string(self):
        """Test string truncation."""
        text = "This is a long text that needs to be truncated"

        truncated = truncate_string(text, 20)
        self.assertEqual(len(truncated), 20)
        self.assertTrue(truncated.endswith("..."))

        # Test short text
        short_text = "Short"
        self.assertEqual(truncate_string(short_text, 20), "Short")

    def test_format_file_size(self):
        """Test file size formatting."""
        self.assertEqual(format_file_size(0), "0 B")
        self.assertEqual(format_file_size(1024), "1.0 KB")
        self.assertEqual(format_file_size(1048576), "1.0 MB")
        self.assertEqual(format_file_size(1073741824), "1.0 GB")

    def test_get_client_ip(self):
        """Test client IP extraction."""
        request = Mock()
        request.META = {"REMOTE_ADDR": "192.168.1.2"}
        request.headers = {"x-forwarded-for": "192.168.1.1,10.0.0.1"}

        ip = get_client_ip(request)
        self.assertEqual(ip, "192.168.1.1")

        # Test without X-Forwarded-For
        request = Mock()
        request.META = {"REMOTE_ADDR": "192.168.1.2"}
        request.headers = {}
        ip = get_client_ip(request)
        self.assertEqual(ip, "192.168.1.2")

    def test_get_user_agent(self):
        """Test user agent extraction."""
        request = Mock()
        request.headers = {"user-agent": "Mozilla/5.0 Test Browser"}

        user_agent = get_user_agent(request)
        self.assertEqual(user_agent, "Mozilla/5.0 Test Browser")

        # Test without user agent
        request = Mock()
        request.headers = {}
        user_agent = get_user_agent(request)
        self.assertEqual(user_agent, "")

    def test_time_since_creation(self):
        """Test time since creation formatting."""
        now = timezone.now()

        # Test days
        days_ago = now - timedelta(days=5)
        self.assertEqual(time_since_creation(days_ago), "5 days ago")

        # Test hours
        hours_ago = now - timedelta(hours=3)
        result = time_since_creation(hours_ago)
        self.assertTrue(result.endswith("hours ago"))

        # Test minutes
        minutes_ago = now - timedelta(minutes=30)
        result = time_since_creation(minutes_ago)
        self.assertTrue(result.endswith("minutes ago"))

        # Test recent
        recent = now - timedelta(seconds=10)
        self.assertEqual(time_since_creation(recent), "Just now")

    @patch("apps.core.utils.send_mail")
    def test_send_notification_email_success(self, mock_send_mail):
        """Test successful email sending."""
        mock_send_mail.return_value = True

        result = send_notification_email(
            "Test Subject", "Test Message", ["test@example.com"]
        )

        self.assertTrue(result)
        mock_send_mail.assert_called_once()

    @patch("apps.core.utils.send_mail")
    def test_send_notification_email_failure(self, mock_send_mail):
        """Test email sending failure."""
        mock_send_mail.side_effect = Exception("Email failed")

        result = send_notification_email(
            "Test Subject", "Test Message", ["test@example.com"], fail_silently=True
        )

        self.assertFalse(result)

    def test_mask_email(self):
        """Test email masking."""
        self.assertEqual(mask_email("test@example.com"), "t**t@example.com")
        self.assertEqual(mask_email("ab@example.com"), "a*@example.com")
        self.assertEqual(mask_email("a@example.com"), "a@example.com")
        self.assertEqual(mask_email("invalid-email"), "invalid-email")

    def test_validate_json_structure(self):
        """Test JSON structure validation."""
        data = {"field1": "value1", "field2": "value2"}
        required_fields = ["field1", "field2", "field3"]

        errors = validate_json_structure(data, required_fields)

        self.assertIn("field3", errors)
        self.assertEqual(errors["field3"], "Field 'field3' is required")

        # Test valid data
        valid_data = {"field1": "value1", "field2": "value2", "field3": "value3"}
        errors = validate_json_structure(valid_data, required_fields)
        self.assertEqual(errors, {})

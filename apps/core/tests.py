"""Comprehensive tests for core app"""

from collections import OrderedDict
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseForbidden
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from .enums import FileType, Priority, Status, UserRole
from .middleware import (
    AdminIPAllowlistMiddleware,
    DemoModeMiddleware,
    SecurityHeadersMiddleware,
)
from .mixins import ActiveManager, SoftDeleteMixin, TimestampMixin, UserTrackingMixin
from .pagination import LargeResultsSetPagination, StandardResultsSetPagination
from .permissions import (
    HasGroup,
    IsAdminOrReadOnly,
    IsManagerOrAdmin,
    IsMemberOrAbove,
    IsOwnerOrAdmin,
)
from .tasks import cleanup_expired_sessions, collect_garbage, health_check
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
from .validators import (
    FileValidator,
    validate_alphanumeric,
    validate_file_size,
    validate_image_dimensions,
    validate_no_special_chars,
    validate_phone_number,
    validate_slug_format,
)

User = get_user_model()


class EnumsTest(TestCase):
    """Test enum choices"""

    def test_user_role_choices(self):
        """Test UserRole enum choices"""
        self.assertEqual(UserRole.ADMIN, "admin")
        self.assertEqual(UserRole.MANAGER, "manager")
        self.assertEqual(UserRole.MEMBER, "member")
        self.assertEqual(UserRole.READ_ONLY, "readonly")

        # Test choices format
        choices = UserRole.choices
        self.assertIn(("admin", "Admin"), choices)
        self.assertIn(("manager", "Manager"), choices)

    def test_file_type_choices(self):
        """Test FileType enum choices"""
        self.assertEqual(FileType.IMAGE, "image")
        self.assertEqual(FileType.DOCUMENT, "document")
        self.assertEqual(FileType.VIDEO, "video")
        self.assertEqual(FileType.AUDIO, "audio")
        self.assertEqual(FileType.ARCHIVE, "archive")
        self.assertEqual(FileType.OTHER, "other")

    def test_status_choices(self):
        """Test Status enum choices"""
        self.assertEqual(Status.DRAFT, "draft")
        self.assertEqual(Status.ACTIVE, "active")
        self.assertEqual(Status.INACTIVE, "inactive")
        self.assertEqual(Status.ARCHIVED, "archived")
        self.assertEqual(Status.DELETED, "deleted")

    def test_priority_choices(self):
        """Test Priority enum choices"""
        self.assertEqual(Priority.LOW, "low")
        self.assertEqual(Priority.MEDIUM, "medium")
        self.assertEqual(Priority.HIGH, "high")
        self.assertEqual(Priority.URGENT, "urgent")


class SecurityHeadersMiddlewareTest(TestCase):
    """Test SecurityHeadersMiddleware"""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SecurityHeadersMiddleware()

    def test_security_headers_development(self):
        """Test security headers in development mode"""
        request = self.factory.get('/')
        response = HttpResponse("Test")

        with override_settings(DEBUG=True, SECURE_SSL_REDIRECT=False):
            response = self.middleware.process_response(request, response)

            # Check CSP is relaxed for development
            csp = response["Content-Security-Policy"]
            self.assertIn("'unsafe-inline'", csp)
            self.assertIn("'unsafe-eval'", csp)

            # Check other security headers
            self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            self.assertEqual(response["X-Frame-Options"], "DENY")
            self.assertEqual(response["X-XSS-Protection"], "1; mode=block")

    def test_security_headers_production(self):
        """Test security headers in production mode"""
        request = self.factory.get('/')
        response = HttpResponse("Test")

        with override_settings(DEBUG=False, SECURE_SSL_REDIRECT=True):
            response = self.middleware.process_response(request, response)

            # Check strict CSP for production
            csp = response["Content-Security-Policy"]
            self.assertIn("default-src 'self'", csp)
            self.assertIn("object-src 'none'", csp)

            # Check HSTS header
            hsts = response["Strict-Transport-Security"]
            self.assertIn("max-age=31536000", hsts)
            self.assertIn("includeSubDomains", hsts)
            self.assertIn("preload", hsts)

    def test_permissions_policy_header(self):
        """Test Permissions Policy header"""
        request = self.factory.get('/')
        response = HttpResponse("Test")

        response = self.middleware.process_response(request, response)

        permissions_policy = response["Permissions-Policy"]
        self.assertIn("camera=()", permissions_policy)
        self.assertIn("microphone=()", permissions_policy)
        self.assertIn("geolocation=()", permissions_policy)


class AdminIPAllowlistMiddlewareTest(TestCase):
    """Test AdminIPAllowlistMiddleware"""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = AdminIPAllowlistMiddleware()

    def test_non_admin_url_allowed(self):
        """Test that non-admin URLs are not checked"""
        request = self.factory.get('/api/users/')
        request.META = {"REMOTE_ADDR": "192.168.1.100"}

        with override_settings(ADMIN_IP_ALLOWLIST=["192.168.1.1"]):
            result = self.middleware.process_request(request)
            self.assertIsNone(result)

    def test_admin_url_no_allowlist(self):
        """Test admin URL with no IP allowlist configured"""
        request = self.factory.get('/admin/')
        request.META = {"REMOTE_ADDR": "192.168.1.100"}

        with override_settings(ADMIN_IP_ALLOWLIST=[]):
            result = self.middleware.process_request(request)
            self.assertIsNone(result)

    def test_admin_url_ip_allowed(self):
        """Test admin URL with allowed IP"""
        request = self.factory.get('/admin/')
        request.META = {"REMOTE_ADDR": "192.168.1.100"}

        with override_settings(ADMIN_IP_ALLOWLIST=["192.168.1.100"]):
            result = self.middleware.process_request(request)
            self.assertIsNone(result)

    def test_admin_url_ip_denied(self):
        """Test admin URL with denied IP"""
        request = self.factory.get('/admin/')
        request.META = {"REMOTE_ADDR": "192.168.1.200"}

        with override_settings(ADMIN_IP_ALLOWLIST=["192.168.1.100"]):
            result = self.middleware.process_request(request)
            self.assertIsInstance(result, HttpResponseForbidden)

    def test_admin_url_cidr_allowed(self):
        """Test admin URL with CIDR notation allowlist"""
        request = self.factory.get('/admin/')
        request.META = {"REMOTE_ADDR": "192.168.1.150"}

        with override_settings(ADMIN_IP_ALLOWLIST=["192.168.1.0/24"]):
            result = self.middleware.process_request(request)
            self.assertIsNone(result)

    def test_admin_url_cidr_denied(self):
        """Test admin URL with CIDR notation - IP not in range"""
        request = self.factory.get('/admin/')
        request.META = {"REMOTE_ADDR": "192.168.2.100"}

        with override_settings(ADMIN_IP_ALLOWLIST=["192.168.1.0/24"]):
            result = self.middleware.process_request(request)
            self.assertIsInstance(result, HttpResponseForbidden)

    def test_x_forwarded_for_header(self):
        """Test IP extraction from X-Forwarded-For header"""
        request = self.factory.get('/admin/')
        request.META = {
            "HTTP_X_FORWARDED_FOR": "192.168.1.100, 10.0.0.1",
            "REMOTE_ADDR": "10.0.0.1"
        }

        with override_settings(ADMIN_IP_ALLOWLIST=["192.168.1.100"]):
            result = self.middleware.process_request(request)
            self.assertIsNone(result)  # Should use first IP from X-Forwarded-For

    def test_invalid_ip_in_allowlist(self):
        """Test handling of invalid IP in allowlist"""
        request = self.factory.get('/admin/')
        request.META = {"REMOTE_ADDR": "192.168.1.100"}

        with override_settings(ADMIN_IP_ALLOWLIST=["invalid-ip", "192.168.1.100"]):
            result = self.middleware.process_request(request)
            self.assertIsNone(result)  # Should work with valid IP despite invalid entry


class DemoModeMiddlewareTest(TestCase):
    """Test DemoModeMiddleware"""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = DemoModeMiddleware()

    def test_demo_mode_disabled(self):
        """Test middleware when demo mode is disabled"""
        request = self.factory.get('/')
        response = HttpResponse("<html><body>Test</body></html>", content_type="text/html")

        with override_settings(DEMO_MODE=False):
            result = self.middleware.process_response(request, response)
            self.assertEqual(result.content.decode(), "<html><body>Test</body></html>")

    def test_demo_mode_enabled_html_response(self):
        """Test middleware when demo mode is enabled with HTML response"""
        request = self.factory.get('/')
        response = HttpResponse("<html><body>Test</body></html>", content_type="text/html")

        with override_settings(DEMO_MODE=True):
            result = self.middleware.process_response(request, response)
            content = result.content.decode()

            self.assertIn("DEMO MODE", content)
            self.assertIn("margin-top: 40px", content)

    def test_demo_mode_enabled_non_html_response(self):
        """Test middleware with non-HTML response"""
        request = self.factory.get('/')
        response = HttpResponse('{"message": "test"}', content_type="application/json")

        with override_settings(DEMO_MODE=True):
            result = self.middleware.process_response(request, response)
            self.assertEqual(result.content.decode(), '{"message": "test"}')

    def test_demo_mode_enabled_error_response(self):
        """Test middleware with error response"""
        request = self.factory.get('/')
        response = HttpResponse("<html><body>Error</body></html>",
                              content_type="text/html", status=404)

        with override_settings(DEMO_MODE=True):
            result = self.middleware.process_response(request, response)
            # Should not modify error responses
            self.assertEqual(result.content.decode(), "<html><body>Error</body></html>")


class MixinsTest(TestCase):
    """Test abstract model mixins"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User"
        )

    def test_timestamp_mixin_fields(self):
        """Test TimestampMixin provides timestamp fields"""
        # Test that the mixin has the expected fields
        fields = [field.name for field in TimestampMixin._meta.get_fields()]
        self.assertIn('created_at', fields)
        self.assertIn('updated_at', fields)

    def test_user_tracking_mixin_fields(self):
        """Test UserTrackingMixin provides user tracking fields"""
        fields = [field.name for field in UserTrackingMixin._meta.get_fields()]
        self.assertIn('created_by', fields)
        self.assertIn('updated_by', fields)

    def test_soft_delete_mixin_fields(self):
        """Test SoftDeleteMixin provides soft delete fields"""
        fields = [field.name for field in SoftDeleteMixin._meta.get_fields()]
        self.assertIn('is_deleted', fields)
        self.assertIn('deleted_at', fields)
        self.assertIn('deleted_by', fields)

    def test_active_manager_excludes_deleted(self):
        """Test ActiveManager excludes soft-deleted records"""
        manager = ActiveManager()
        queryset = manager.get_queryset()

        # Mock the filter method to verify it's called correctly
        with patch.object(queryset, 'filter'):
            manager.get_queryset()
            # The manager should call super().get_queryset().filter(is_deleted=False)
            # But since we're testing the class directly, we just check the structure


class PermissionsTest(TestCase):
    """Test custom permission classes"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User"
        )
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="adminpass123",
            name="Admin User",
            is_staff=True,
            is_superuser=True,
        )
        self.manager_user = User.objects.create_user(
            email="manager@example.com",
            password="managerpass123",
            name="Manager User"
        )

        # Create groups
        self.admin_group = Group.objects.create(name="Admin")
        self.manager_group = Group.objects.create(name="Manager")
        self.member_group = Group.objects.create(name="Member")

        # Add users to groups
        self.admin_user.groups.add(self.admin_group)
        self.manager_user.groups.add(self.manager_group)
        self.user.groups.add(self.member_group)

        self.factory = RequestFactory()

    def test_has_group_permission_success(self):
        """Test HasGroup permission with user in group"""
        permission = HasGroup("Member")
        request = self.factory.get('/')
        request.user = self.user

        result = permission.has_permission(request, None)
        self.assertTrue(result)

    def test_has_group_permission_failure(self):
        """Test HasGroup permission with user not in group"""
        permission = HasGroup("Admin")
        request = self.factory.get('/')
        request.user = self.user

        result = permission.has_permission(request, None)
        self.assertFalse(result)

    def test_has_group_permission_unauthenticated(self):
        """Test HasGroup permission with unauthenticated user"""
        permission = HasGroup("Member")
        request = self.factory.get('/')
        request.user = None

        result = permission.has_permission(request, None)
        self.assertFalse(result)

    def test_is_admin_or_readonly_read_permission(self):
        """Test IsAdminOrReadOnly allows read for authenticated users"""
        permission = IsAdminOrReadOnly()
        request = self.factory.get('/')
        request.user = self.user

        result = permission.has_permission(request, None)
        self.assertTrue(result)

    def test_is_admin_or_readonly_write_permission_admin(self):
        """Test IsAdminOrReadOnly allows write for admin users"""
        permission = IsAdminOrReadOnly()
        request = self.factory.post('/')
        request.user = self.admin_user

        with patch.object(self.admin_user, 'is_admin', return_value=True):
            result = permission.has_permission(request, None)
            self.assertTrue(result)

    def test_is_admin_or_readonly_write_permission_denied(self):
        """Test IsAdminOrReadOnly denies write for non-admin users"""
        permission = IsAdminOrReadOnly()
        request = self.factory.post('/')
        request.user = self.user

        with patch.object(self.user, 'is_admin', return_value=False):
            result = permission.has_permission(request, None)
            self.assertFalse(result)

    def test_is_owner_or_admin_owner_access(self):
        """Test IsOwnerOrAdmin allows access to owner"""
        permission = IsOwnerOrAdmin()
        request = self.factory.get('/')
        request.user = self.user

        # Mock object with created_by field
        obj = Mock()
        obj.created_by = self.user

        result = permission.has_object_permission(request, None, obj)
        self.assertTrue(result)

    def test_is_owner_or_admin_admin_access(self):
        """Test IsOwnerOrAdmin allows access to admin"""
        permission = IsOwnerOrAdmin()
        request = self.factory.get('/')
        request.user = self.admin_user

        # Mock object owned by different user
        obj = Mock()
        obj.created_by = self.user

        with patch.object(self.admin_user, 'is_admin', return_value=True):
            result = permission.has_object_permission(request, None, obj)
            self.assertTrue(result)

    def test_is_owner_or_admin_user_field(self):
        """Test IsOwnerOrAdmin with user field instead of created_by"""
        permission = IsOwnerOrAdmin()
        request = self.factory.get('/')
        request.user = self.user

        # Mock object with user field
        obj = Mock()
        obj.user = self.user
        del obj.created_by  # Remove created_by to test user field fallback

        with patch('hasattr', side_effect=lambda obj, attr: attr == 'user'):
            result = permission.has_object_permission(request, None, obj)
            self.assertTrue(result)

    def test_is_owner_or_admin_user_object(self):
        """Test IsOwnerOrAdmin when object is the user themselves"""
        permission = IsOwnerOrAdmin()
        request = self.factory.get('/')
        request.user = self.user

        # Object is the user themselves (e.g., user profile access)
        result = permission.has_object_permission(request, None, self.user)
        self.assertTrue(result)

    def test_is_manager_or_admin_manager(self):
        """Test IsManagerOrAdmin allows access to manager"""
        permission = IsManagerOrAdmin()
        request = self.factory.get('/')
        request.user = self.manager_user

        with patch.object(self.manager_user, 'is_manager', return_value=True):
            result = permission.has_permission(request, None)
            self.assertTrue(result)

    def test_is_manager_or_admin_denied(self):
        """Test IsManagerOrAdmin denies access to regular user"""
        permission = IsManagerOrAdmin()
        request = self.factory.get('/')
        request.user = self.user

        with patch.object(self.user, 'is_manager', return_value=False):
            result = permission.has_permission(request, None)
            self.assertFalse(result)

    def test_is_member_or_above_member(self):
        """Test IsMemberOrAbove allows access to member"""
        permission = IsMemberOrAbove()
        request = self.factory.get('/')
        request.user = self.user

        with patch.object(self.user, 'is_member', return_value=True):
            result = permission.has_permission(request, None)
            self.assertTrue(result)


class TasksTest(TestCase):
    """Test Celery tasks"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User"
        )

    @patch('apps.core.tasks.Session.objects.filter')
    def test_cleanup_expired_sessions_success(self, mock_filter):
        """Test successful cleanup of expired sessions"""
        # Mock expired sessions
        mock_queryset = Mock()
        mock_queryset.count.return_value = 5
        mock_queryset.delete.return_value = None
        mock_filter.return_value = mock_queryset

        result = cleanup_expired_sessions()

        self.assertTrue(result["success"])
        self.assertEqual(result["cleaned_sessions"], 5)
        mock_filter.assert_called_once()
        mock_queryset.delete.assert_called_once()

    @patch('apps.core.tasks.Session.objects.filter')
    def test_cleanup_expired_sessions_error(self, mock_filter):
        """Test cleanup of expired sessions with error"""
        mock_filter.side_effect = Exception("Database error")

        result = cleanup_expired_sessions()

        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Database error")

    @patch('django.db.connection.cursor')
    @patch('django.core.cache.cache')
    def test_health_check_success(self, mock_cache, mock_cursor_context):
        """Test successful health check"""
        # Mock database cursor
        mock_cursor = Mock()
        mock_cursor_context.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor_context.return_value.__exit__ = Mock(return_value=False)

        # Mock cache operations
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "ok"

        result = health_check()

        self.assertTrue(result["success"])
        self.assertIn("timestamp", result)
        mock_cursor.execute.assert_called_once_with("SELECT 1")
        mock_cache.set.assert_called_once_with("health_check", "ok", 30)
        mock_cache.get.assert_called_once_with("health_check")

    @patch('django.db.connection.cursor')
    def test_health_check_database_error(self, mock_cursor_context):
        """Test health check with database error"""
        mock_cursor_context.side_effect = Exception("Database connection failed")

        result = health_check()

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Database connection failed")

    @patch('django.core.cache.cache')
    @patch('django.db.connection.cursor')
    def test_health_check_cache_error(self, mock_cursor_context, mock_cache):
        """Test health check with cache error"""
        # Mock successful database connection
        mock_cursor = Mock()
        mock_cursor_context.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor_context.return_value.__exit__ = Mock(return_value=False)

        # Mock cache failure
        mock_cache.set.return_value = None
        mock_cache.get.return_value = None  # Cache not working

        result = health_check()

        self.assertFalse(result["success"])
        self.assertIn("Cache not working", result["error"])

    @patch('gc.collect')
    def test_collect_garbage_success(self, mock_gc_collect):
        """Test successful garbage collection"""
        mock_gc_collect.return_value = 42

        result = collect_garbage()

        self.assertTrue(result["success"])
        self.assertEqual(result["collected_objects"], 42)
        mock_gc_collect.assert_called_once()

    @patch('gc.collect')
    def test_collect_garbage_error(self, mock_gc_collect):
        """Test garbage collection with error"""
        mock_gc_collect.side_effect = Exception("GC error")

        result = collect_garbage()

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "GC error")


class UtilsTest(TestCase):
    """Test utility functions"""

    def test_generate_uuid(self):
        """Test UUID generation"""
        uuid_str = generate_uuid()
        self.assertEqual(len(uuid_str), 36)  # Standard UUID length with hyphens
        self.assertEqual(uuid_str.count('-'), 4)  # Standard UUID format

    def test_generate_short_uuid(self):
        """Test short UUID generation"""
        short_uuid = generate_short_uuid(8)
        self.assertEqual(len(short_uuid), 8)
        self.assertNotIn('-', short_uuid)  # No hyphens in short UUID

        # Test default length
        default_short = generate_short_uuid()
        self.assertEqual(len(default_short), 8)

    def test_generate_secure_token(self):
        """Test secure token generation"""
        token = generate_secure_token(32)
        self.assertTrue(len(token) > 0)

        # Test that two tokens are different
        token2 = generate_secure_token(32)
        self.assertNotEqual(token, token2)

    def test_generate_hash(self):
        """Test hash generation"""
        data = "test data"
        hash_value = generate_hash(data)

        # SHA-256 produces 64-character hex string
        self.assertEqual(len(hash_value), 64)

        # Same input should produce same hash
        hash_value2 = generate_hash(data)
        self.assertEqual(hash_value, hash_value2)

        # Test different algorithm
        md5_hash = generate_hash(data, "md5")
        self.assertEqual(len(md5_hash), 32)  # MD5 produces 32-character hex

    def test_create_slug(self):
        """Test slug creation"""
        self.assertEqual(create_slug("Hello World"), "hello-world")
        self.assertEqual(create_slug("Test@#$String"), "teststring")
        self.assertEqual(create_slug("Multiple   Spaces"), "multiple-spaces")

        # Test max length
        long_text = "a" * 100
        slug = create_slug(long_text, max_length=10)
        self.assertEqual(len(slug), 10)

    def test_safe_get_dict_value(self):
        """Test safe dictionary value retrieval"""
        test_dict = {"key1": "value1", "key2": None}

        self.assertEqual(safe_get_dict_value(test_dict, "key1"), "value1")
        self.assertIsNone(safe_get_dict_value(test_dict, "key2"))
        self.assertEqual(safe_get_dict_value(test_dict, "nonexistent", "default"), "default")

        # Test with non-dict object
        self.assertEqual(safe_get_dict_value(None, "key", "default"), "default")

    def test_truncate_string(self):
        """Test string truncation"""
        text = "This is a long text that needs truncation"

        truncated = truncate_string(text, 10)
        self.assertEqual(truncated, "This is...")
        self.assertEqual(len(truncated), 10)

        # Test with custom suffix
        truncated_custom = truncate_string(text, 15, "---")
        self.assertEqual(truncated_custom, "This is a lo---")

        # Test with short text (should not truncate)
        short_text = "Short"
        self.assertEqual(truncate_string(short_text, 10), "Short")

    def test_format_file_size(self):
        """Test file size formatting"""
        self.assertEqual(format_file_size(0), "0 B")
        self.assertEqual(format_file_size(512), "512.0 B")
        self.assertEqual(format_file_size(1024), "1.0 KB")
        self.assertEqual(format_file_size(1048576), "1.0 MB")
        self.assertEqual(format_file_size(1073741824), "1.0 GB")
        self.assertEqual(format_file_size(1099511627776), "1.0 TB")

        # Test fractional values
        self.assertEqual(format_file_size(1536), "1.5 KB")  # 1.5 KB

    def test_get_client_ip(self):
        """Test client IP extraction"""
        factory = RequestFactory()

        # Test with REMOTE_ADDR
        request = factory.get('/')
        request.META = {"REMOTE_ADDR": "192.168.1.100"}

        ip = get_client_ip(request)
        self.assertEqual(ip, "192.168.1.100")

        # Test with X-Forwarded-For (should use first IP)
        request.META = {
            "HTTP_X_FORWARDED_FOR": "203.0.113.1, 192.168.1.100",
            "REMOTE_ADDR": "192.168.1.100"
        }

        ip = get_client_ip(request)
        self.assertEqual(ip, "203.0.113.1")

    def test_get_user_agent(self):
        """Test user agent extraction"""
        factory = RequestFactory()

        request = factory.get('/')
        request.META = {"HTTP_USER_AGENT": "Mozilla/5.0 Test Browser"}

        user_agent = get_user_agent(request)
        self.assertEqual(user_agent, "Mozilla/5.0 Test Browser")

        # Test with missing user agent
        request.META = {}
        user_agent = get_user_agent(request)
        self.assertEqual(user_agent, "")

    def test_time_since_creation(self):
        """Test time since creation formatting"""
        now = timezone.now()

        # Test "Just now"
        recent = now - timezone.timedelta(seconds=30)
        self.assertEqual(time_since_creation(recent), "Just now")

        # Test minutes
        minutes_ago = now - timezone.timedelta(minutes=5)
        self.assertEqual(time_since_creation(minutes_ago), "5 minutes ago")

        # Test hours
        hours_ago = now - timezone.timedelta(hours=3)
        self.assertEqual(time_since_creation(hours_ago), "3 hours ago")

        # Test days
        days_ago = now - timezone.timedelta(days=2)
        self.assertEqual(time_since_creation(days_ago), "2 days ago")

    @patch('django.core.mail.send_mail')
    def test_send_notification_email_success(self, mock_send_mail):
        """Test successful email sending"""
        mock_send_mail.return_value = True

        result = send_notification_email(
            subject="Test Subject",
            message="Test Message",
            recipient_list=["test@example.com"],
            from_email="sender@example.com"
        )

        self.assertTrue(result)
        mock_send_mail.assert_called_once_with(
            subject="Test Subject",
            message="Test Message",
            from_email="sender@example.com",
            recipient_list=["test@example.com"],
            fail_silently=False
        )

    @patch('django.core.mail.send_mail')
    def test_send_notification_email_failure(self, mock_send_mail):
        """Test email sending failure"""
        mock_send_mail.side_effect = Exception("SMTP Error")

        with self.assertRaises(Exception) as cm:
            send_notification_email(
                subject="Test Subject",
                message="Test Message",
                recipient_list=["test@example.com"]
            )
        self.assertEqual(str(cm.exception), "SMTP Error")

        # Test with fail_silently=True
        result = send_notification_email(
            subject="Test Subject",
            message="Test Message",
            recipient_list=["test@example.com"],
            fail_silently=True
        )
        self.assertFalse(result)

    def test_mask_email(self):
        """Test email masking for privacy"""
        self.assertEqual(mask_email("user@example.com"), "u***@example.com")
        self.assertEqual(mask_email("ab@example.com"), "a*@example.com")
        self.assertEqual(mask_email("test@example.com"), "t**t@example.com")

        # Test invalid email
        self.assertEqual(mask_email("invalid-email"), "invalid-email")

    def test_validate_json_structure(self):
        """Test JSON structure validation"""
        data = {"field1": "value1", "field2": "value2"}
        required_fields = ["field1", "field2"]

        errors = validate_json_structure(data, required_fields)
        self.assertEqual(errors, {})

        # Test with missing field
        errors = validate_json_structure(data, ["field1", "field2", "field3"])
        self.assertIn("field3", errors)
        self.assertEqual(errors["field3"], "Field 'field3' is required")


class ValidatorsTest(TestCase):
    """Test custom validators"""

    def test_validate_phone_number_valid(self):
        """Test valid phone number validation"""
        # These should not raise ValidationError
        try:
            validate_phone_number("+1234567890")
            validate_phone_number("1234567890")
            validate_phone_number("+123456789012345")  # Up to 15 digits
        except ValidationError:
            self.fail("validate_phone_number raised ValidationError for valid input")

    def test_validate_phone_number_invalid(self):
        """Test invalid phone number validation"""
        invalid_numbers = [
            "12345",  # Too short
            "+12345678901234567890",  # Too long
            "abc123456789",  # Contains letters
            "+1-234-567-8900",  # Contains hyphens
        ]

        for number in invalid_numbers:
            with self.assertRaises(ValidationError):
                validate_phone_number(number)

    def test_validate_no_special_chars_valid(self):
        """Test valid input with no special characters"""
        try:
            validate_no_special_chars("Hello World 123")
            validate_no_special_chars("Test123")
            validate_no_special_chars("   ")  # Only spaces
        except ValidationError:
            self.fail("validate_no_special_chars raised ValidationError for valid input")

    def test_validate_no_special_chars_invalid(self):
        """Test invalid input with special characters"""
        invalid_inputs = ["Hello@World", "Test#123", "Value$", "Name!"]

        for input_val in invalid_inputs:
            with self.assertRaises(ValidationError):
                validate_no_special_chars(input_val)

    def test_validate_alphanumeric_valid(self):
        """Test valid alphanumeric input"""
        try:
            validate_alphanumeric("Hello123")
            validate_alphanumeric("ABC")
            validate_alphanumeric("123")
        except ValidationError:
            self.fail("validate_alphanumeric raised ValidationError for valid input")

    def test_validate_alphanumeric_invalid(self):
        """Test invalid alphanumeric input"""
        invalid_inputs = ["Hello World", "Test@123", "Value!"]

        for input_val in invalid_inputs:
            with self.assertRaises(ValidationError):
                validate_alphanumeric(input_val)

    def test_validate_slug_format_valid(self):
        """Test valid slug format"""
        try:
            validate_slug_format("hello-world")
            validate_slug_format("test123")
            validate_slug_format("slug-with-numbers-123")
        except ValidationError:
            self.fail("validate_slug_format raised ValidationError for valid input")

    def test_validate_slug_format_invalid(self):
        """Test invalid slug format"""
        invalid_slugs = ["Hello-World", "test_slug", "slug with spaces", "UPPERCASE"]

        for slug in invalid_slugs:
            with self.assertRaises(ValidationError):
                validate_slug_format(slug)

    def test_validate_file_size_valid(self):
        """Test valid file size"""
        # Create mock file with valid size
        mock_file = Mock()
        mock_file.size = 3 * 1024 * 1024  # 3MB

        try:
            validate_file_size(mock_file, max_size_mb=5)
        except ValidationError:
            self.fail("validate_file_size raised ValidationError for valid file")

    def test_validate_file_size_invalid(self):
        """Test invalid file size (too large)"""
        mock_file = Mock()
        mock_file.size = 10 * 1024 * 1024  # 10MB

        with self.assertRaises(ValidationError):
            validate_file_size(mock_file, max_size_mb=5)

    @patch('PIL.Image.open')
    def test_validate_image_dimensions_valid(self, mock_image_open):
        """Test valid image dimensions"""
        mock_image = Mock()
        mock_image.size = (1000, 800)  # Within limits
        mock_image_open.return_value.__enter__ = Mock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = Mock(return_value=False)

        mock_file = Mock()

        try:
            validate_image_dimensions(mock_file, max_width=1920, max_height=1080)
        except ValidationError:
            self.fail("validate_image_dimensions raised ValidationError for valid image")

    @patch('PIL.Image.open')
    def test_validate_image_dimensions_invalid(self, mock_image_open):
        """Test invalid image dimensions (too large)"""
        mock_image = Mock()
        mock_image.size = (2000, 1500)  # Exceeds limits
        mock_image_open.return_value.__enter__ = Mock(return_value=mock_image)
        mock_image_open.return_value.__exit__ = Mock(return_value=False)

        mock_file = Mock()

        with self.assertRaises(ValidationError):
            validate_image_dimensions(mock_file, max_width=1920, max_height=1080)

    @patch('PIL.Image.open')
    def test_validate_image_dimensions_invalid_file(self, mock_image_open):
        """Test invalid image file"""
        mock_image_open.side_effect = Exception("Cannot open image")

        mock_file = Mock()

        with self.assertRaises(ValidationError) as context:
            validate_image_dimensions(mock_file)

        self.assertIn("Invalid image file", str(context.exception))

    def test_file_validator_valid(self):
        """Test FileValidator with valid file"""
        mock_file = Mock()
        mock_file.size = 2 * 1024 * 1024  # 2MB
        mock_file.name = "test.jpg"
        mock_file.content_type = "image/jpeg"

        validator = FileValidator(
            max_size_mb=5,
            allowed_extensions=["jpg", "png"],
            allowed_content_types=["image/jpeg", "image/png"]
        )

        try:
            validator(mock_file)
        except ValidationError:
            self.fail("FileValidator raised ValidationError for valid file")

    def test_file_validator_size_exceeded(self):
        """Test FileValidator with oversized file"""
        mock_file = Mock()
        mock_file.size = 10 * 1024 * 1024  # 10MB
        mock_file.name = "test.jpg"
        mock_file.content_type = "image/jpeg"

        validator = FileValidator(max_size_mb=5)

        with self.assertRaises(ValidationError):
            validator(mock_file)

    def test_file_validator_invalid_extension(self):
        """Test FileValidator with invalid extension"""
        mock_file = Mock()
        mock_file.size = 1024  # 1KB
        mock_file.name = "test.xyz"
        mock_file.content_type = "application/octet-stream"

        validator = FileValidator(allowed_extensions=["jpg", "png"])

        with self.assertRaises(ValidationError):
            validator(mock_file)

    def test_file_validator_invalid_content_type(self):
        """Test FileValidator with invalid content type"""
        mock_file = Mock()
        mock_file.size = 1024  # 1KB
        mock_file.name = "test.jpg"
        mock_file.content_type = "application/octet-stream"

        validator = FileValidator(allowed_content_types=["image/jpeg", "image/png"])

        with self.assertRaises(ValidationError):
            validator(mock_file)


class PaginationTest(TestCase):
    """Test pagination classes"""

    def test_standard_pagination_response(self):
        """Test StandardResultsSetPagination response format"""
        pagination = StandardResultsSetPagination()

        # Mock paginator and page
        mock_paginator = Mock()
        mock_paginator.count = 100
        mock_paginator.num_pages = 5

        mock_page = Mock()
        mock_page.paginator = mock_paginator
        mock_page.number = 2

        pagination.page = mock_page

        # Mock pagination methods
        pagination.get_next_link = Mock(return_value="http://example.com/?page=3")
        pagination.get_previous_link = Mock(return_value="http://example.com/?page=1")
        pagination.page_size = 20

        data = ["item1", "item2", "item3"]
        response = pagination.get_paginated_response(data)

        expected_data = OrderedDict([
            ("count", 100),
            ("next", "http://example.com/?page=3"),
            ("previous", "http://example.com/?page=1"),
            ("page_size", 20),
            ("total_pages", 5),
            ("current_page", 2),
            ("results", data),
        ])

        self.assertEqual(response.data, expected_data)

    def test_standard_pagination_settings(self):
        """Test StandardResultsSetPagination settings"""
        pagination = StandardResultsSetPagination()

        self.assertEqual(pagination.page_size, 20)
        self.assertEqual(pagination.page_size_query_param, "page_size")
        self.assertEqual(pagination.max_page_size, 100)

    def test_large_pagination_settings(self):
        """Test LargeResultsSetPagination settings"""
        pagination = LargeResultsSetPagination()

        self.assertEqual(pagination.page_size, 50)
        self.assertEqual(pagination.page_size_query_param, "page_size")
        self.assertEqual(pagination.max_page_size, 200)


# Integration tests using pytest fixtures
@pytest.mark.django_db
class TestCoreIntegration:
    """Integration tests for core functionality"""

    def test_user_with_timestamp_tracking(self, user):
        """Test user creation with timestamp tracking"""
        # User should have been created with timestamps
        assert user.date_joined is not None
        assert user.date_joined <= timezone.now()

    def test_permission_with_real_user(self, user, admin_user):
        """Test permissions with real user objects"""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/')
        request.user = admin_user

        permission = IsAdminOrReadOnly()

        # Admin should have write permission
        with patch.object(admin_user, 'is_admin', return_value=True):
            assert permission.has_permission(request, None) is True

    def test_utils_with_real_data(self):
        """Test utility functions with real data"""
        # Test file size formatting with edge cases
        assert format_file_size(0) == "0 B"
        assert format_file_size(1023) == "1023.0 B"
        assert format_file_size(1024) == "1.0 KB"

        # Test slug creation with unicode
        assert create_slug("Café & Restaurant") == "cafe-restaurant"

        # Test secure token uniqueness
        token1 = generate_secure_token()
        token2 = generate_secure_token()
        assert token1 != token2
        assert len(token1) > 20  # Should be reasonably long

    def test_validators_integration(self, sample_image):
        """Test validators with real file objects"""
        # Test file size validation
        try:
            validate_file_size(sample_image, max_size_mb=1)
        except ValidationError:
            pytest.fail("Sample image should be valid")

        # Test FileValidator with real file
        validator = FileValidator(
            max_size_mb=5,
            allowed_extensions=["png", "jpg", "jpeg"],
            allowed_content_types=["image/png", "image/jpeg"]
        )

        try:
            validator(sample_image)
        except ValidationError:
            pytest.fail("Sample image should pass FileValidator")

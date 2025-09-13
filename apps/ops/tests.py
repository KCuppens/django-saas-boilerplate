"""Test cases for operations and monitoring functionality."""

import json
from datetime import datetime, timedelta
from unittest.mock import Mock, mock_open, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, TestCase

from apps.api.models import Note
from apps.emails.models import EmailMessageLog, EmailTemplate

from .metrics import health_metrics, prometheus_metrics
from .tasks import (
    backup_database,
    cleanup_old_backups,
    health_check_task,
    system_maintenance,
)
from .views import health_check, liveness_check, readiness_check, version_info

User = get_user_model()


class OpsViewsTestCase(TestCase):
    """Test ops views."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()

    def test_health_check_view(self):
        """Test health check endpoint."""
        request = self.factory.get("/health/")
        response = health_check(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, JsonResponse)

        data = json.loads(response.content)
        self.assertEqual(data["status"], "ok")
        self.assertIn("timestamp", data)
        self.assertEqual(data["service"], "django-saas-boilerplate")

    def test_liveness_check_view(self):
        """Test liveness check endpoint."""
        request = self.factory.get("/alive/")
        response = liveness_check(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, JsonResponse)

        data = json.loads(response.content)
        self.assertEqual(data["status"], "alive")
        self.assertIn("timestamp", data)

    def test_readiness_check_success(self):
        """Test readiness check with successful checks."""
        request = self.factory.get("/ready/")

        # Clear cache first to ensure clean test
        cache.clear()

        response = readiness_check(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "ready")
        self.assertTrue(data["checks"]["database"])
        self.assertTrue(data["checks"]["cache"])

    @patch("apps.ops.views.connection")
    def test_readiness_check_database_failure(self, mock_connection):
        """Test readiness check with database failure."""
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        request = self.factory.get("/ready/")
        response = readiness_check(request)

        self.assertEqual(response.status_code, 503)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "not_ready")
        self.assertFalse(data["checks"]["database"])

    @patch("apps.ops.views.cache")
    def test_readiness_check_cache_failure(self, mock_cache):
        """Test readiness check with cache failure."""
        mock_cache.set.return_value = None
        mock_cache.get.return_value = None  # Cache failed

        request = self.factory.get("/ready/")
        response = readiness_check(request)

        self.assertEqual(response.status_code, 503)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "not_ready")
        self.assertTrue(data["checks"]["database"])
        self.assertFalse(data["checks"]["cache"])

    @patch("apps.ops.views.subprocess.check_output")
    def test_version_info_with_git(self, mock_subprocess):
        """Test version info endpoint with git information."""
        mock_subprocess.side_effect = [
            b"abc123def456\n",  # git hash
            b"main\n",  # git branch
        ]

        request = self.factory.get("/version/")
        response = version_info(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(data["git_hash"], "abc123def456")
        self.assertEqual(data["git_branch"], "main")

    @patch("apps.ops.views.subprocess.check_output")
    def test_version_info_git_failure(self, mock_subprocess):
        """Test version info endpoint when git fails."""
        mock_subprocess.side_effect = Exception("Git not found")

        request = self.factory.get("/version/")
        response = version_info(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["version"], "1.0.0")
        self.assertNotIn("git_hash", data)
        self.assertNotIn("git_branch", data)


class OpsMetricsTestCase(TestCase):
    """Test metrics endpoints."""

    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )

        # Create test data for metrics
        Note.objects.create(
            title="Test Note",
            content="Test content",
            is_public=True,
            created_by=self.user,
            updated_by=self.user,
        )

        EmailTemplate.objects.create(
            key="test",
            subject="Test Subject",
            html_body="<p>Test</p>",
            text_body="Test",
            created_by=self.user,
            updated_by=self.user,
        )

        EmailMessageLog.objects.create(
            template_key="test",
            to_email="test@example.com",
            subject="Test Email",
            status="sent",
            created_by=self.user,
            updated_by=self.user,
        )

    def test_prometheus_metrics_success(self):
        """Test prometheus metrics endpoint with successful data collection."""
        request = self.factory.get("/metrics/")
        response = prometheus_metrics(request)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(
            response["content-type"], "text/plain; version=0.0.4; charset=utf-8"
        )

        content = response.content.decode("utf-8")

        # Check for user metrics
        self.assertIn("django_users_total", content)
        self.assertIn("django_users_active", content)

        # Check for notes metrics
        self.assertIn("django_notes_total", content)
        self.assertIn("django_notes_public", content)

        # Check for email metrics
        self.assertIn("django_emails_total", content)
        self.assertIn("django_emails_sent", content)

        # Check for timestamp
        self.assertIn("django_metrics_timestamp", content)

    @patch("apps.ops.metrics.User.objects.count")
    def test_prometheus_metrics_database_error(self, mock_count):
        """Test prometheus metrics with database error."""
        mock_count.side_effect = Exception("Database error")

        request = self.factory.get("/metrics/")
        response = prometheus_metrics(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Should contain error fallback metrics
        self.assertIn("django_app_status 0", content)
        self.assertIn("Error:", content)

    def test_health_metrics_all_healthy(self):
        """Test health metrics with all systems healthy."""
        request = self.factory.get("/health-metrics/")
        response = health_metrics(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Should show healthy status
        self.assertIn("django_health_status 1", content)
        self.assertIn("django_health_database 1", content)
        self.assertIn("django_health_cache 1", content)

    @patch("apps.ops.metrics.connection")
    def test_health_metrics_database_unhealthy(self, mock_connection):
        """Test health metrics with database failure."""
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        request = self.factory.get("/health-metrics/")
        response = health_metrics(request)

        content = response.content.decode("utf-8")

        # Should show unhealthy status
        self.assertIn("django_health_status 0", content)
        self.assertIn("django_health_database 0", content)

    @patch("apps.ops.metrics.cache")
    def test_health_metrics_cache_failure(self, mock_cache):
        """Test health metrics with cache failure."""
        mock_cache.set.return_value = None
        mock_cache.get.return_value = None

        request = self.factory.get("/health-metrics/")
        response = health_metrics(request)

        content = response.content.decode("utf-8")

        # Cache should be marked as unhealthy
        self.assertIn("django_health_cache 0", content)

    @patch("apps.ops.metrics.psutil")
    def test_prometheus_metrics_with_psutil(self, mock_psutil):
        """Test prometheus metrics with system metrics."""
        # Mock psutil responses
        mock_memory = Mock()
        mock_memory.percent = 75.0
        mock_memory.available = 2147483648  # 2GB
        mock_memory.total = 8589934592  # 8GB

        mock_psutil.boot_time.return_value = 1640995200  # Mock boot time
        mock_psutil.virtual_memory.return_value = mock_memory
        mock_psutil.cpu_percent.return_value = 45.0

        request = self.factory.get("/metrics/")
        response = prometheus_metrics(request)

        content = response.content.decode("utf-8")

        # Should include system metrics
        self.assertIn("system_uptime_seconds", content)
        self.assertIn("system_memory_usage_percent 75.0", content)
        self.assertIn("system_cpu_usage_percent 45.0", content)


class OpsTasksTestCase(TestCase):
    """Test ops tasks."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )

    @patch("apps.ops.tasks.settings")
    @patch("apps.ops.tasks.subprocess.run")
    @patch("apps.ops.tasks.os.makedirs")
    def test_backup_database_postgresql(
        self, mock_makedirs, mock_subprocess, mock_settings
    ):
        """Test database backup for PostgreSQL."""
        # Mock settings
        mock_settings.BASE_DIR = "/app"
        mock_settings.DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "test_db",
                "USER": "test_user",
                "PASSWORD": "test_pass",
                "HOST": "localhost",
                "PORT": 5432,
            }
        }

        # Mock successful subprocess run
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        result = backup_database()

        self.assertTrue(result["success"])
        self.assertIn("backup_file", result)
        self.assertIn("backup_path", result)
        mock_makedirs.assert_called_once()
        mock_subprocess.assert_called_once()

    @patch("apps.ops.tasks.settings")
    @patch("apps.ops.tasks.subprocess.run")
    def test_backup_database_postgresql_failure(self, mock_subprocess, mock_settings):
        """Test database backup failure for PostgreSQL."""
        mock_settings.BASE_DIR = "/app"
        mock_settings.DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "test_db",
                "USER": "test_user",
                "PASSWORD": "test_pass",
            }
        }

        # Mock failed subprocess run
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "pg_dump: error"
        mock_subprocess.return_value = mock_result

        result = backup_database()

        self.assertFalse(result["success"])
        self.assertIn("error", result)

    @patch("apps.ops.tasks.settings")
    @patch("apps.ops.tasks.call_command")
    @patch("builtins.open", new_callable=mock_open)
    def test_backup_database_sqlite(self, mock_file, mock_call_command, mock_settings):
        """Test database backup for SQLite."""
        mock_settings.BASE_DIR = "/app"
        mock_settings.DATABASES = {
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "test.db"}
        }

        result = backup_database()

        self.assertTrue(result["success"])
        mock_call_command.assert_called_once_with(
            "dumpdata", stdout=mock_file.return_value, indent=2
        )

    @patch("apps.ops.tasks.settings")
    @patch("apps.ops.tasks.glob.glob")
    @patch("apps.ops.tasks.os.stat")
    @patch("apps.ops.tasks.os.remove")
    @patch("apps.ops.tasks.os.path.exists")
    def test_cleanup_old_backups(
        self, mock_exists, mock_remove, mock_stat, mock_glob, mock_settings
    ):
        """Test cleanup of old backup files."""
        mock_settings.BASE_DIR = "/app"
        mock_exists.return_value = True

        # Mock old backup files
        mock_glob.return_value = ["/app/backups/backup_20220101_120000.sql"]

        # Mock file stats (old file)
        mock_file_stat = Mock()
        mock_file_stat.st_mtime = (datetime.now() - timedelta(days=10)).timestamp()
        mock_stat.return_value = mock_file_stat

        result = cleanup_old_backups(days_to_keep=7)

        self.assertTrue(result["success"])
        self.assertEqual(result["cleaned_files"], 1)
        mock_remove.assert_called_once()

    @patch("apps.ops.tasks.settings")
    @patch("apps.ops.tasks.os.path.exists")
    def test_cleanup_old_backups_no_directory(self, mock_exists, mock_settings):
        """Test cleanup when backup directory doesn't exist."""
        mock_settings.BASE_DIR = "/app"
        mock_exists.return_value = False

        result = cleanup_old_backups()

        self.assertTrue(result["success"])
        self.assertEqual(result["cleaned_files"], 0)
        self.assertIn("does not exist", result["message"])

    @patch("apps.ops.tasks.call_command")
    @patch("apps.ops.tasks.cache")
    @patch("apps.ops.tasks.settings")
    def test_system_maintenance_success(
        self, mock_settings, mock_cache, mock_call_command
    ):
        """Test successful system maintenance."""
        mock_settings.DEBUG = False

        result = system_maintenance()

        self.assertTrue(result["success"])
        self.assertTrue(result["maintenance_results"]["clear_sessions"])
        self.assertTrue(result["maintenance_results"]["collect_static"])
        self.assertTrue(result["maintenance_results"]["clear_cache"])

        # Verify commands were called
        mock_call_command.assert_any_call("clearsessions")
        mock_call_command.assert_any_call("collectstatic", "--noinput", "--clear")
        mock_cache.clear.assert_called_once()

    @patch("apps.ops.tasks.call_command")
    @patch("apps.ops.tasks.settings")
    def test_system_maintenance_debug_mode(self, mock_settings, mock_call_command):
        """Test system maintenance in debug mode."""
        mock_settings.DEBUG = True

        result = system_maintenance()

        self.assertTrue(result["success"])
        # Should not collect static in debug mode
        self.assertNotIn("collect_static", result["maintenance_results"])

    @patch("apps.ops.tasks.call_command")
    def test_system_maintenance_command_failure(self, mock_call_command):
        """Test system maintenance with command failure."""
        mock_call_command.side_effect = Exception("Command failed")

        result = system_maintenance()

        self.assertTrue(result["success"])
        # Should contain error message
        self.assertIn("Error:", str(result["maintenance_results"]["clear_sessions"]))

    @patch("apps.ops.tasks.shutil.disk_usage")
    @patch("apps.ops.tasks.cache")
    @patch("apps.ops.tasks.connection")
    @patch("apps.ops.tasks.settings")
    def test_health_check_task_all_healthy(
        self, mock_settings, mock_connection, mock_cache, mock_disk
    ):
        """Test health check task with all systems healthy."""
        mock_settings.BASE_DIR = "/app"

        # Mock database success
        mock_cursor = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock cache success
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "ok"

        # Mock disk usage (5GB free)
        mock_disk_usage = Mock()
        mock_disk_usage.free = 5 * (1024**3)
        mock_disk.return_value = mock_disk_usage

        result = health_check_task()

        self.assertTrue(result["success"])
        self.assertEqual(result["health_results"]["overall_health"], "healthy")
        self.assertTrue(result["health_results"]["checks"]["database"])
        self.assertTrue(result["health_results"]["checks"]["cache"])
        self.assertTrue(result["health_results"]["checks"]["disk_space"]["sufficient"])

    @patch("apps.ops.tasks.connection")
    def test_health_check_task_database_failure(self, mock_connection):
        """Test health check task with database failure."""
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        result = health_check_task()

        self.assertTrue(result["success"])
        self.assertEqual(result["health_results"]["overall_health"], "unhealthy")
        self.assertIn("Error:", str(result["health_results"]["checks"]["database"]))

    @patch("apps.ops.tasks.shutil.disk_usage")
    @patch("apps.ops.tasks.settings")
    def test_health_check_task_low_disk_space(self, mock_settings, mock_disk):
        """Test health check task with low disk space."""
        mock_settings.BASE_DIR = "/app"

        # Mock low disk space (500MB free)
        mock_disk_usage = Mock()
        mock_disk_usage.free = 500 * (1024**2)  # 500MB
        mock_disk.return_value = mock_disk_usage

        result = health_check_task()

        self.assertTrue(result["success"])
        self.assertEqual(result["health_results"]["overall_health"], "unhealthy")
        self.assertFalse(result["health_results"]["checks"]["disk_space"]["sufficient"])

    @patch("apps.ops.tasks.connection")
    def test_health_check_task_exception(self, mock_connection):
        """Test health check task with unexpected exception."""
        mock_connection.cursor.side_effect = Exception("Unexpected error")

        result = health_check_task()

        self.assertFalse(result["success"])
        self.assertIn("error", result)

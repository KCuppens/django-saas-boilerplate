"""Comprehensive tests for core Celery tasks."""

import gc
import logging
from unittest.mock import MagicMock, Mock, patch

from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.core.tasks import cleanup_expired_sessions, collect_garbage, health_check


class CleanupExpiredSessionsTaskTest(TestCase):
    """Test cleanup_expired_sessions task."""

    def setUp(self):
        """Set up test data."""
        # Clear any existing test data
        Session.objects.all().delete()

        # Create test sessions
        self.current_time = timezone.now()
        self.expired_time = self.current_time - timezone.timedelta(days=1)
        self.valid_time = self.current_time + timezone.timedelta(days=1)

    @patch("apps.core.tasks.logger")
    def test_cleanup_expired_sessions_success(self, mock_logger):
        """Test successful cleanup of expired sessions."""
        # Mock Session objects and queryset
        mock_queryset = Mock()
        mock_queryset.count.return_value = 2
        mock_queryset.delete.return_value = (2, {"django.contrib.sessions.Session": 2})

        with (
            patch("apps.core.tasks.Session.objects.filter") as mock_filter,
            patch("apps.core.tasks.timezone.now") as mock_now,
        ):
            mock_now.return_value = self.current_time
            mock_filter.return_value = mock_queryset

            result = cleanup_expired_sessions()

        # Verify the filter was called with correct parameters
        mock_filter.assert_called_once_with(expire_date__lt=self.current_time)
        mock_queryset.count.assert_called_once()
        mock_queryset.delete.assert_called_once()

        # Verify logging
        mock_logger.info.assert_called_once_with("Cleaned up %d expired sessions", 2)

        # Verify return value
        expected_result = {"success": True, "cleaned_sessions": 2}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    def test_cleanup_expired_sessions_no_expired_sessions(self, mock_logger):
        """Test cleanup when no expired sessions exist."""
        mock_queryset = Mock()
        mock_queryset.count.return_value = 0
        mock_queryset.delete.return_value = (0, {})

        with (
            patch("apps.core.tasks.Session.objects.filter") as mock_filter,
            patch("apps.core.tasks.timezone.now") as mock_now,
        ):
            mock_now.return_value = self.current_time
            mock_filter.return_value = mock_queryset

            result = cleanup_expired_sessions()

        # Verify logging
        mock_logger.info.assert_called_once_with("Cleaned up %d expired sessions", 0)

        # Verify return value
        expected_result = {"success": True, "cleaned_sessions": 0}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    def test_cleanup_expired_sessions_database_error(self, mock_logger):
        """Test cleanup with database error."""
        with (
            patch("apps.core.tasks.Session.objects.filter") as mock_filter,
            patch("apps.core.tasks.timezone.now") as mock_now,
        ):
            mock_now.return_value = self.current_time
            mock_filter.side_effect = DatabaseError("Database connection failed")

            result = cleanup_expired_sessions()

        # Verify error logging
        mock_logger.error.assert_called_once_with(
            "Failed to cleanup expired sessions: %s", "Database connection failed"
        )

        # Verify return value
        expected_result = {"success": False, "error": "Database connection failed"}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    def test_cleanup_expired_sessions_delete_error(self, mock_logger):
        """Test cleanup with delete operation error."""
        mock_queryset = Mock()
        mock_queryset.count.return_value = 5
        mock_queryset.delete.side_effect = IntegrityError("Foreign key constraint")

        with (
            patch("apps.core.tasks.Session.objects.filter") as mock_filter,
            patch("apps.core.tasks.timezone.now") as mock_now,
        ):
            mock_now.return_value = self.current_time
            mock_filter.return_value = mock_queryset

            result = cleanup_expired_sessions()

        # Verify error logging
        mock_logger.error.assert_called_once_with(
            "Failed to cleanup expired sessions: %s", "Foreign key constraint"
        )

        # Verify return value
        expected_result = {"success": False, "error": "Foreign key constraint"}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    def test_cleanup_expired_sessions_timezone_error(self, mock_logger):
        """Test cleanup with timezone error."""
        with patch("apps.core.tasks.timezone.now") as mock_now:
            mock_now.side_effect = Exception("Timezone error")

            result = cleanup_expired_sessions()

        # Verify error logging
        mock_logger.error.assert_called_once_with(
            "Failed to cleanup expired sessions: %s", "Timezone error"
        )

        # Verify return value
        expected_result = {"success": False, "error": "Timezone error"}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    def test_cleanup_expired_sessions_large_batch(self, mock_logger):
        """Test cleanup with large number of expired sessions."""
        mock_queryset = Mock()
        mock_queryset.count.return_value = 10000
        mock_queryset.delete.return_value = (
            10000,
            {"django.contrib.sessions.Session": 10000},
        )

        with (
            patch("apps.core.tasks.Session.objects.filter") as mock_filter,
            patch("apps.core.tasks.timezone.now") as mock_now,
        ):
            mock_now.return_value = self.current_time
            mock_filter.return_value = mock_queryset

            result = cleanup_expired_sessions()

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Cleaned up %d expired sessions", 10000
        )

        # Verify return value
        expected_result = {"success": True, "cleaned_sessions": 10000}
        self.assertEqual(result, expected_result)


class HealthCheckTaskTest(TestCase):
    """Test health_check task."""

    def setUp(self):
        """Set up test data."""
        self.current_time = timezone.now()

    @patch("apps.core.tasks.logger")
    @patch("django.core.cache.cache")
    @patch("django.db.connection")
    def test_health_check_success(self, mock_connection, mock_cache, mock_logger):
        """Test successful health check."""
        # Mock database connection
        mock_cursor = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock cache operations
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "ok"

        with patch("apps.core.tasks.timezone.now") as mock_now:
            mock_now.return_value = self.current_time

            result = health_check()

        # Verify database check
        mock_cursor.execute.assert_called_once_with("SELECT 1")

        # Verify cache operations
        mock_cache.set.assert_called_once_with("health_check", "ok", 30)
        mock_cache.get.assert_called_once_with("health_check")

        # Verify logging
        mock_logger.info.assert_called_once_with("Health check passed")

        # Verify return value
        expected_result = {"success": True, "timestamp": self.current_time.isoformat()}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    @patch("django.core.cache.cache")
    @patch("django.db.connection")
    def test_health_check_database_failure(
        self, mock_connection, mock_cache, mock_logger
    ):
        """Test health check with database failure."""
        # Mock database connection failure
        mock_connection.cursor.side_effect = DatabaseError("Database unavailable")

        result = health_check()

        # Verify error logging
        mock_logger.error.assert_called_once_with(
            "Health check failed: %s", "Database unavailable"
        )

        # Verify return value
        expected_result = {"success": False, "error": "Database unavailable"}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    @patch("django.core.cache.cache")
    @patch("django.db.connection")
    def test_health_check_cache_set_failure(
        self, mock_connection, mock_cache, mock_logger
    ):
        """Test health check with cache set failure."""
        # Mock successful database connection
        mock_cursor = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock cache set failure
        mock_cache.set.side_effect = Exception("Cache server down")

        result = health_check()

        # Verify database check was attempted
        mock_cursor.execute.assert_called_once_with("SELECT 1")

        # Verify error logging
        mock_logger.error.assert_called_once_with(
            "Health check failed: %s", "Cache server down"
        )

        # Verify return value
        expected_result = {"success": False, "error": "Cache server down"}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    @patch("django.core.cache.cache")
    @patch("django.db.connection")
    def test_health_check_cache_get_failure(
        self, mock_connection, mock_cache, mock_logger
    ):
        """Test health check with cache get failure."""
        # Mock successful database connection
        mock_cursor = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock cache operations - set succeeds, get fails
        mock_cache.set.return_value = None
        mock_cache.get.side_effect = Exception("Cache read error")

        result = health_check()

        # Verify database check was attempted
        mock_cursor.execute.assert_called_once_with("SELECT 1")

        # Verify cache set was attempted
        mock_cache.set.assert_called_once_with("health_check", "ok", 30)

        # Verify error logging
        mock_logger.error.assert_called_once_with(
            "Health check failed: %s", "Cache read error"
        )

        # Verify return value
        expected_result = {"success": False, "error": "Cache read error"}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    @patch("django.core.cache.cache")
    @patch("django.db.connection")
    def test_health_check_cache_value_mismatch(
        self, mock_connection, mock_cache, mock_logger
    ):
        """Test health check with cache value mismatch."""
        # Mock successful database connection
        mock_cursor = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock cache operations - set succeeds, get returns wrong value
        mock_cache.set.return_value = None
        mock_cache.get.return_value = "wrong_value"

        result = health_check()

        # Verify database and cache operations
        mock_cursor.execute.assert_called_once_with("SELECT 1")
        mock_cache.set.assert_called_once_with("health_check", "ok", 30)
        mock_cache.get.assert_called_once_with("health_check")

        # Verify error logging
        mock_logger.error.assert_called_once_with(
            "Health check failed: %s", "Cache not working"
        )

        # Verify return value
        expected_result = {"success": False, "error": "Cache not working"}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    def test_health_check_general_exception(self, mock_logger):
        """Test health check with general exception during execution."""
        with patch("django.db.connection") as mock_connection:
            # Mock a general exception during database connection setup
            mock_connection.cursor.side_effect = RuntimeError("System error")

            result = health_check()

        # Verify error logging
        mock_logger.error.assert_called_once_with(
            "Health check failed: %s", "System error"
        )

        # Verify return value
        expected_result = {"success": False, "error": "System error"}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    @patch("django.core.cache.cache")
    @patch("django.db.connection")
    def test_health_check_database_cursor_context_error(
        self, mock_connection, mock_cache, mock_logger
    ):
        """Test health check with database cursor context manager error."""
        # Mock database connection context manager failure
        mock_connection.cursor.return_value.__enter__.side_effect = Exception(
            "Context error"
        )

        result = health_check()

        # Verify error logging
        mock_logger.error.assert_called_once_with(
            "Health check failed: %s", "Context error"
        )

        # Verify return value
        expected_result = {"success": False, "error": "Context error"}
        self.assertEqual(result, expected_result)


class CollectGarbageTaskTest(TestCase):
    """Test collect_garbage task."""

    @patch("apps.core.tasks.logger")
    @patch("gc.collect")
    def test_collect_garbage_success(self, mock_gc_collect, mock_logger):
        """Test successful garbage collection."""
        mock_gc_collect.return_value = 42

        result = collect_garbage()

        # Verify gc.collect was called
        mock_gc_collect.assert_called_once()

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Garbage collection completed, collected %d objects", 42
        )

        # Verify return value
        expected_result = {"success": True, "collected_objects": 42}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    @patch("gc.collect")
    def test_collect_garbage_no_objects(self, mock_gc_collect, mock_logger):
        """Test garbage collection when no objects are collected."""
        mock_gc_collect.return_value = 0

        result = collect_garbage()

        # Verify gc.collect was called
        mock_gc_collect.assert_called_once()

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Garbage collection completed, collected %d objects", 0
        )

        # Verify return value
        expected_result = {"success": True, "collected_objects": 0}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    @patch("gc.collect")
    def test_collect_garbage_large_collection(self, mock_gc_collect, mock_logger):
        """Test garbage collection with large number of collected objects."""
        mock_gc_collect.return_value = 10000

        result = collect_garbage()

        # Verify gc.collect was called
        mock_gc_collect.assert_called_once()

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Garbage collection completed, collected %d objects", 10000
        )

        # Verify return value
        expected_result = {"success": True, "collected_objects": 10000}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    @patch("gc.collect")
    def test_collect_garbage_exception(self, mock_gc_collect, mock_logger):
        """Test garbage collection with exception."""
        mock_gc_collect.side_effect = Exception("Memory error")

        result = collect_garbage()

        # Verify gc.collect was called
        mock_gc_collect.assert_called_once()

        # Verify error logging
        mock_logger.error.assert_called_once_with(
            "Garbage collection failed: %s", "Memory error"
        )

        # Verify return value
        expected_result = {"success": False, "error": "Memory error"}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    @patch("gc.collect")
    def test_collect_garbage_import_error(self, mock_gc_collect, mock_logger):
        """Test garbage collection with gc module import issue."""
        # This tests the scenario where gc module might have issues
        mock_gc_collect.side_effect = ImportError("gc module not available")

        result = collect_garbage()

        # Verify error logging
        mock_logger.error.assert_called_once_with(
            "Garbage collection failed: %s", "gc module not available"
        )

        # Verify return value
        expected_result = {"success": False, "error": "gc module not available"}
        self.assertEqual(result, expected_result)

    @patch("apps.core.tasks.logger")
    def test_collect_garbage_gc_import_failure(self, mock_logger):
        """Test collect_garbage with gc import failure at module level."""
        # This tests what would happen if the gc import itself failed
        # We simulate this by patching the task function to raise ImportError
        with patch("gc.collect") as mock_collect:
            mock_collect.side_effect = AttributeError(
                "module 'gc' has no attribute 'collect'"
            )

            result = collect_garbage()

            # Verify error logging
            mock_logger.error.assert_called_once_with(
                "Garbage collection failed: %s",
                "module 'gc' has no attribute 'collect'",
            )

            # Verify return value
            expected_result = {
                "success": False,
                "error": "module 'gc' has no attribute 'collect'",
            }
            self.assertEqual(result, expected_result)


class TaskIntegrationTest(TestCase):
    """Integration tests for core tasks."""

    def setUp(self):
        """Set up test data."""
        self.current_time = timezone.now()

    @patch("apps.core.tasks.logger")
    def test_all_tasks_return_consistent_format(self, mock_logger):
        """Test that all tasks return consistent response format."""
        # Mock successful scenarios for all tasks
        with (
            patch("apps.core.tasks.Session.objects.filter") as mock_session_filter,
            patch("apps.core.tasks.timezone.now") as mock_now,
            patch("django.db.connection") as mock_connection,
            patch("django.core.cache.cache") as mock_cache,
            patch("gc.collect") as mock_gc_collect,
        ):
            mock_now.return_value = self.current_time

            # Setup cleanup_expired_sessions
            mock_queryset = Mock()
            mock_queryset.count.return_value = 5
            mock_queryset.delete.return_value = (5, {})
            mock_session_filter.return_value = mock_queryset

            # Setup health_check
            mock_cursor = Mock()
            mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cache.set.return_value = None
            mock_cache.get.return_value = "ok"

            # Setup collect_garbage
            mock_gc_collect.return_value = 10

            # Test each task
            cleanup_result = cleanup_expired_sessions()
            health_result = health_check()
            garbage_result = collect_garbage()

            # Verify all tasks return success boolean
            self.assertIn("success", cleanup_result)
            self.assertIn("success", health_result)
            self.assertIn("success", garbage_result)

            self.assertTrue(cleanup_result["success"])
            self.assertTrue(health_result["success"])
            self.assertTrue(garbage_result["success"])

            # Verify specific return fields
            self.assertIn("cleaned_sessions", cleanup_result)
            self.assertIn("timestamp", health_result)
            self.assertIn("collected_objects", garbage_result)

    @patch("apps.core.tasks.logger")
    def test_all_tasks_error_handling_consistent(self, mock_logger):
        """Test that all tasks handle errors consistently."""
        # Test error scenarios for all tasks
        error_message = "Test error"

        # Test cleanup_expired_sessions error
        with patch("apps.core.tasks.Session.objects.filter") as mock_filter:
            mock_filter.side_effect = Exception(error_message)
            result = cleanup_expired_sessions()

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], error_message)

        # Test health_check error
        with patch("django.db.connection") as mock_connection:
            mock_connection.cursor.side_effect = Exception(error_message)
            result = health_check()

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], error_message)

        # Test collect_garbage error
        with patch("gc.collect") as mock_collect:
            mock_collect.side_effect = Exception(error_message)
            result = collect_garbage()

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], error_message)

    def test_task_logging_levels(self):
        """Test that tasks use appropriate logging levels."""
        with (
            patch("apps.core.tasks.logger") as mock_logger,
            patch("apps.core.tasks.Session.objects.filter") as mock_filter,
            patch("apps.core.tasks.timezone.now") as mock_now,
        ):
            mock_now.return_value = self.current_time

            # Test successful operation uses info level
            mock_queryset = Mock()
            mock_queryset.count.return_value = 1
            mock_queryset.delete.return_value = (1, {})
            mock_filter.return_value = mock_queryset

            cleanup_expired_sessions()
            mock_logger.info.assert_called()

            # Reset mock
            mock_logger.reset_mock()

            # Test error operation uses error level
            mock_filter.side_effect = Exception("Test error")
            cleanup_expired_sessions()
            mock_logger.error.assert_called()

    def test_task_exception_handling_robustness(self):
        """Test that tasks handle various types of exceptions gracefully."""
        test_exceptions = [
            DatabaseError("Database error"),
            ConnectionError("Connection error"),
            TimeoutError("Timeout error"),
            ValueError("Value error"),
            RuntimeError("Runtime error"),
            MemoryError("Memory error"),
        ]

        for exception in test_exceptions:
            with (
                self.subTest(exception=type(exception).__name__),
                patch("apps.core.tasks.Session.objects.filter") as mock_filter,
            ):
                mock_filter.side_effect = exception

                result = cleanup_expired_sessions()

                self.assertFalse(result["success"])
                self.assertEqual(result["error"], str(exception))

    @patch("apps.core.tasks.logger")
    def test_concurrent_task_execution_safety(self, mock_logger):
        """Test that tasks are safe for concurrent execution."""
        # This test ensures tasks don't have shared state issues

        # Test multiple cleanup calls with different mock data
        with (
            patch("apps.core.tasks.Session.objects.filter") as mock_filter,
            patch("apps.core.tasks.timezone.now") as mock_now,
        ):
            mock_now.return_value = self.current_time

            # First call
            mock_queryset1 = Mock()
            mock_queryset1.count.return_value = 5
            mock_queryset1.delete.return_value = (5, {})
            mock_filter.return_value = mock_queryset1

            result1 = cleanup_expired_sessions()

            # Second call with different data
            mock_queryset2 = Mock()
            mock_queryset2.count.return_value = 10
            mock_queryset2.delete.return_value = (10, {})
            mock_filter.return_value = mock_queryset2

            result2 = cleanup_expired_sessions()

            # Verify each call got its own result
            self.assertEqual(result1["cleaned_sessions"], 5)
            self.assertEqual(result2["cleaned_sessions"], 10)

            # Verify no shared state contamination
            self.assertNotEqual(
                result1["cleaned_sessions"], result2["cleaned_sessions"]
            )


class TaskRetryAndResilienceTest(TestCase):
    """Test task retry mechanisms and resilience."""

    @patch("apps.core.tasks.logger")
    def test_cleanup_sessions_database_recovery(self, mock_logger):
        """Test cleanup task recovery after database issues."""
        with patch("apps.core.tasks.Session.objects.filter") as mock_filter:
            # First call fails, second succeeds (simulating database recovery)
            mock_queryset = Mock()
            mock_queryset.count.return_value = 3
            mock_queryset.delete.return_value = (3, {})

            mock_filter.side_effect = [
                DatabaseError("Connection lost"),  # First call fails
                mock_queryset,  # Second call succeeds
            ]

            # First attempt should fail
            result1 = cleanup_expired_sessions()
            self.assertFalse(result1["success"])

            # Second attempt should succeed (simulating retry)
            result2 = cleanup_expired_sessions()
            self.assertTrue(result2["success"])
            self.assertEqual(result2["cleaned_sessions"], 3)

    @patch("apps.core.tasks.logger")
    def test_health_check_partial_failure_handling(self, mock_logger):
        """Test health check handling partial system failures."""
        with (
            patch("django.db.connection") as mock_connection,
            patch("django.core.cache.cache") as mock_cache,
            patch("apps.core.tasks.timezone.now") as mock_now,
        ):
            mock_now.return_value = timezone.now()

            # Database works, cache fails
            mock_cursor = Mock()
            mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
            mock_cache.set.side_effect = Exception("Cache unavailable")

            result = health_check()

            # Should fail overall due to cache failure
            self.assertFalse(result["success"])
            self.assertIn("Cache unavailable", result["error"])

    @patch("apps.core.tasks.logger")
    def test_garbage_collection_memory_pressure(self, mock_logger):
        """Test garbage collection under memory pressure conditions."""
        with patch("gc.collect") as mock_collect:
            # Simulate high memory pressure - lots of objects collected
            mock_collect.return_value = 50000

            result = collect_garbage()

            self.assertTrue(result["success"])
            self.assertEqual(result["collected_objects"], 50000)
            mock_logger.info.assert_called_once_with(
                "Garbage collection completed, collected %d objects", 50000
            )

    def test_task_timeout_simulation(self):
        """Test task behavior under timeout conditions."""
        # Simulate long-running operations that might timeout
        with patch("apps.core.tasks.Session.objects.filter") as mock_filter:
            # Mock a query that would timeout
            mock_queryset = Mock()
            mock_queryset.count.side_effect = Exception("Query timeout")
            mock_filter.return_value = mock_queryset

            result = cleanup_expired_sessions()

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "Query timeout")

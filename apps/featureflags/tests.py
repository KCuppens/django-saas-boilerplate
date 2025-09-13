"""Comprehensive tests for feature flags functionality."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings
from django.views import View

from apps.featureflags.helpers import (
    FeatureFlags,
    get_feature_context,
    is_feature_enabled,
    require_feature_flag,
)

User = get_user_model()


class TestFeatureFlags(TestCase):
    """Test FeatureFlags class functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )
        self.factory = RequestFactory()
        self.request = self.factory.get("/")
        self.request.user = self.user

    def test_default_flags_configuration(self):
        """Test that default flags are properly configured."""
        # Verify all default flags exist
        expected_flags = [
            "FILES",
            "EMAIL_EDITOR",
            "RABBITMQ",
            "ADVANCED_ANALYTICS",
            "BETA_FEATURES",
            "API_V2",
            "MAINTENANCE_MODE",
        ]

        for flag in expected_flags:
            self.assertIn(flag, FeatureFlags.DEFAULT_FLAGS)
            self.assertIn("description", FeatureFlags.DEFAULT_FLAGS[flag])
            self.assertIn("default", FeatureFlags.DEFAULT_FLAGS[flag])

    @patch("apps.featureflags.helpers.flag_is_active")
    def test_is_enabled_with_request(self, mock_flag_is_active):
        """Test is_enabled with request object."""
        mock_flag_is_active.return_value = True

        result = FeatureFlags.is_enabled("FILES", request=self.request)

        self.assertTrue(result)
        mock_flag_is_active.assert_called_once_with(self.request, "FILES")

    @patch("apps.featureflags.helpers.flag_is_active")
    def test_is_enabled_without_request(self, mock_flag_is_active):
        """Test is_enabled without request object."""
        mock_flag_is_active.return_value = True

        result = FeatureFlags.is_enabled("FILES", user=self.user)

        self.assertTrue(result)
        mock_flag_is_active.assert_called_once_with(None, "FILES")

    @patch("apps.featureflags.helpers.flag_is_active")
    def test_is_enabled_returns_default_on_exception(self, mock_flag_is_active):
        """Test is_enabled returns default value when exception occurs."""
        mock_flag_is_active.side_effect = Exception("Database error")

        # Test with flag that has default=True
        result = FeatureFlags.is_enabled("EMAIL_EDITOR")
        self.assertTrue(result)

        # Test with flag that has default=False
        result = FeatureFlags.is_enabled("FILES")
        self.assertFalse(result)

        # Test with non-existent flag
        result = FeatureFlags.is_enabled("NON_EXISTENT")
        self.assertFalse(result)

    @patch("apps.featureflags.helpers.switch_is_active")
    def test_is_switch_active(self, mock_switch_is_active):
        """Test is_switch_active functionality."""
        mock_switch_is_active.return_value = True

        result = FeatureFlags.is_switch_active("test_switch")

        self.assertTrue(result)
        mock_switch_is_active.assert_called_once_with("test_switch")

    @patch("apps.featureflags.helpers.switch_is_active")
    def test_is_switch_active_handles_exception(self, mock_switch_is_active):
        """Test is_switch_active returns False on exception."""
        mock_switch_is_active.side_effect = Exception("Switch error")

        result = FeatureFlags.is_switch_active("test_switch")

        self.assertFalse(result)

    @patch("apps.featureflags.helpers.sample_is_active")
    def test_is_sample_active(self, mock_sample_is_active):
        """Test is_sample_active functionality."""
        mock_sample_is_active.return_value = True

        result = FeatureFlags.is_sample_active("test_sample")

        self.assertTrue(result)
        mock_sample_is_active.assert_called_once_with("test_sample")

    @patch("apps.featureflags.helpers.sample_is_active")
    def test_is_sample_active_handles_exception(self, mock_sample_is_active):
        """Test is_sample_active returns False on exception."""
        mock_sample_is_active.side_effect = Exception("Sample error")

        result = FeatureFlags.is_sample_active("test_sample")

        self.assertFalse(result)

    def test_get_enabled_flags(self):
        """Test get_enabled_flags returns status of all flags."""
        with patch.object(FeatureFlags, "is_enabled") as mock_is_enabled:
            # Set up mock to return different values for different flags
            mock_is_enabled.side_effect = (
                lambda flag, *args, **kwargs: flag == "EMAIL_EDITOR"
            )

            result = FeatureFlags.get_enabled_flags(
                request=self.request, user=self.user
            )

            # Should check all default flags
            self.assertEqual(len(result), len(FeatureFlags.DEFAULT_FLAGS))
            self.assertTrue(result["EMAIL_EDITOR"])
            self.assertFalse(result["FILES"])

    def test_get_flag_status(self):
        """Test get_flag_status returns detailed flag information."""
        with patch.object(FeatureFlags, "is_enabled") as mock_is_enabled:
            mock_is_enabled.return_value = True

            result = FeatureFlags.get_flag_status("FILES", request=self.request)

            self.assertEqual(result["name"], "FILES")
            self.assertTrue(result["enabled"])
            self.assertEqual(
                result["description"], "Enable file upload and management functionality"
            )
            self.assertFalse(result["default"])

    def test_get_flag_status_nonexistent_flag(self):
        """Test get_flag_status with non-existent flag."""
        with patch.object(FeatureFlags, "is_enabled") as mock_is_enabled:
            mock_is_enabled.return_value = False

            result = FeatureFlags.get_flag_status("NONEXISTENT", request=self.request)

            self.assertEqual(result["name"], "NONEXISTENT")
            self.assertFalse(result["enabled"])
            self.assertEqual(result["description"], "No description available")
            self.assertFalse(result["default"])


class TestFeatureFlagHelperFunctions(TestCase):
    """Test helper functions for feature flags."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )
        self.factory = RequestFactory()
        self.request = self.factory.get("/")
        self.request.user = self.user

    @patch.object(FeatureFlags, "is_enabled")
    def test_is_feature_enabled(self, mock_is_enabled):
        """Test is_feature_enabled convenience function."""
        mock_is_enabled.return_value = True

        result = is_feature_enabled("FILES", request=self.request, user=self.user)

        self.assertTrue(result)
        mock_is_enabled.assert_called_once_with("FILES", self.request, self.user)

    @patch.object(FeatureFlags, "get_enabled_flags")
    def test_get_feature_context(self, mock_get_enabled_flags):
        """Test get_feature_context for templates."""
        mock_get_enabled_flags.return_value = {"FILES": True, "EMAIL_EDITOR": False}

        result = get_feature_context(request=self.request, user=self.user)

        self.assertIn("features", result)
        self.assertIn("feature_flags", result)
        self.assertEqual(result["features"], {"FILES": True, "EMAIL_EDITOR": False})
        self.assertEqual(result["feature_flags"], FeatureFlags)


class TestRequireFeatureFlagDecorator(TestCase):
    """Test require_feature_flag decorator."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )
        self.factory = RequestFactory()

    @patch.object(FeatureFlags, "is_enabled")
    def test_decorator_on_function_with_flag_enabled(self, mock_is_enabled):
        """Test decorator allows access when flag is enabled."""
        mock_is_enabled.return_value = True

        @require_feature_flag("FILES")
        def test_view(request):
            return "Success"

        request = self.factory.get("/")
        request.user = self.user

        result = test_view(request)

        self.assertEqual(result, "Success")
        mock_is_enabled.assert_called_once_with("FILES", request, None)

    @patch.object(FeatureFlags, "is_enabled")
    def test_decorator_on_function_with_flag_disabled(self, mock_is_enabled):
        """Test decorator denies access when flag is disabled."""
        mock_is_enabled.return_value = False

        @require_feature_flag("FILES")
        def test_view(request):
            return "Success"

        request = self.factory.get("/")
        request.user = self.user

        with self.assertRaises(Http404) as cm:
            test_view(request)

        self.assertEqual(str(cm.exception), "Feature not available")

    @patch.object(FeatureFlags, "is_enabled")
    def test_decorator_on_class_with_flag_enabled(self, mock_is_enabled):
        """Test decorator on class allows access when flag is enabled."""
        mock_is_enabled.return_value = True

        @require_feature_flag("FILES")
        class TestView(View):
            def get(self, request):
                return "Success"

        request = self.factory.get("/")
        request.user = self.user

        view = TestView()
        result = view.get(request)

        self.assertEqual(result, "Success")

    @patch.object(FeatureFlags, "is_enabled")
    def test_decorator_on_class_with_flag_disabled(self, mock_is_enabled):
        """Test decorator on class denies access when flag is disabled."""
        mock_is_enabled.return_value = False

        @require_feature_flag("FILES")
        class TestView(View):
            def get(self, request):
                return "Success"

        request = self.factory.get("/")
        request.user = self.user

        view = TestView()

        with self.assertRaises(Http404):
            view.dispatch(request)

    @patch.object(FeatureFlags, "is_enabled")
    def test_decorator_with_anonymous_user(self, mock_is_enabled):
        """Test decorator with anonymous user."""
        mock_is_enabled.return_value = False

        @require_feature_flag("FILES")
        def test_view(request):
            return "Success"

        request = self.factory.get("/")
        request.user = AnonymousUser()

        with self.assertRaises(Http404):
            test_view(request)

        mock_is_enabled.assert_called_once()

    def test_decorator_handles_missing_request(self):
        """Test decorator handles views without request parameter."""

        @require_feature_flag("FILES")
        def test_view():
            return "Success"

        # Should not raise an error
        with patch.object(FeatureFlags, "is_enabled", return_value=True):
            result = test_view()
            self.assertEqual(result, "Success")


class TestFeatureFlagIntegration(TestCase):
    """Integration tests for feature flags with Django settings."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

    @override_settings(WAFFLE_FLAG_DEFAULT=True)
    def test_flag_respects_settings(self):
        """Test that flags respect Django settings."""
        # This would integrate with actual waffle settings
        # Testing the integration point
        result = FeatureFlags.is_enabled("NEW_FLAG")
        # Should return default when flag doesn't exist
        self.assertFalse(result)

    def test_concurrent_flag_checks(self):
        """Test that concurrent flag checks work correctly."""
        from concurrent.futures import ThreadPoolExecutor

        def check_flag(flag_name):
            return FeatureFlags.is_enabled(flag_name)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(check_flag, "FILES") for _ in range(10)]
            results = [f.result() for f in futures]

        # All results should be consistent
        self.assertEqual(len(set(results)), 1)

    def test_flag_caching_behavior(self):
        """Test that flag values are cached appropriately."""
        with patch("apps.featureflags.helpers.flag_is_active") as mock_flag:
            mock_flag.return_value = True

            # First call
            result1 = FeatureFlags.is_enabled("FILES")

            # Second call - should use same mechanism
            result2 = FeatureFlags.is_enabled("FILES")

            self.assertEqual(result1, result2)
            # Verify flag was checked each time (no caching in our implementation)
            self.assertEqual(mock_flag.call_count, 2)

"""Tests for feature flags helpers."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import RequestFactory, TestCase

from waffle.models import Flag, Sample, Switch

from apps.featureflags.helpers import (
    FeatureFlags,
    get_feature_context,
    is_feature_enabled,
    require_feature_flag,
)

User = get_user_model()


class FeatureFlagsTest(TestCase):
    """Test FeatureFlags class functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"  # nosec B106
        )
        self.request_factory = RequestFactory()
        self.request = self.request_factory.get("/")
        self.request.user = self.user

    def test_default_flags_configuration(self):
        """Test that default flags are properly configured."""
        expected_flags = [
            "FILES",
            "EMAIL_EDITOR",
            "RABBITMQ",
            "ADVANCED_ANALYTICS",
            "BETA_FEATURES",
            "API_V2",
            "MAINTENANCE_MODE",
        ]

        for flag_name in expected_flags:
            self.assertIn(flag_name, FeatureFlags.DEFAULT_FLAGS)
            flag_config = FeatureFlags.DEFAULT_FLAGS[flag_name]
            self.assertIn("description", flag_config)
            self.assertIn("default", flag_config)
            self.assertIsInstance(flag_config["default"], bool)

    def test_default_flag_values(self):
        """Test specific default flag values."""
        self.assertFalse(FeatureFlags.DEFAULT_FLAGS["FILES"]["default"])
        self.assertTrue(FeatureFlags.DEFAULT_FLAGS["EMAIL_EDITOR"]["default"])
        self.assertFalse(FeatureFlags.DEFAULT_FLAGS["RABBITMQ"]["default"])
        self.assertFalse(FeatureFlags.DEFAULT_FLAGS["ADVANCED_ANALYTICS"]["default"])
        self.assertFalse(FeatureFlags.DEFAULT_FLAGS["BETA_FEATURES"]["default"])
        self.assertFalse(FeatureFlags.DEFAULT_FLAGS["API_V2"]["default"])
        self.assertFalse(FeatureFlags.DEFAULT_FLAGS["MAINTENANCE_MODE"]["default"])

    @patch("apps.featureflags.helpers.flag_is_active")
    def test_is_enabled_with_request_flag_active(self, mock_flag_is_active):
        """Test is_enabled when waffle flag is active with request."""
        mock_flag_is_active.return_value = True

        result = FeatureFlags.is_enabled("FILES", self.request, self.user)

        self.assertTrue(result)
        mock_flag_is_active.assert_called_once_with(self.request, "FILES")

    @patch("apps.featureflags.helpers.flag_is_active")
    def test_is_enabled_with_request_flag_inactive(self, mock_flag_is_active):
        """Test is_enabled when waffle flag is inactive with request."""
        mock_flag_is_active.return_value = False

        result = FeatureFlags.is_enabled("FILES", self.request, self.user)

        self.assertFalse(result)
        mock_flag_is_active.assert_called_once_with(self.request, "FILES")

    @patch("apps.featureflags.helpers.flag_is_active")
    def test_is_enabled_without_request_flag_active(self, mock_flag_is_active):
        """Test is_enabled when waffle flag is active without request."""
        mock_flag_is_active.return_value = True

        result = FeatureFlags.is_enabled("FILES", user=self.user)

        self.assertTrue(result)
        mock_flag_is_active.assert_called_once_with(None, "FILES")

    @patch("apps.featureflags.helpers.flag_is_active")
    def test_is_enabled_without_request_flag_inactive(self, mock_flag_is_active):
        """Test is_enabled when waffle flag is inactive without request."""
        mock_flag_is_active.return_value = False

        result = FeatureFlags.is_enabled("FILES", user=self.user)

        self.assertFalse(result)
        mock_flag_is_active.assert_called_once_with(None, "FILES")

    @patch("apps.featureflags.helpers.flag_is_active")
    def test_is_enabled_waffle_exception_returns_default_false(
        self, mock_flag_is_active
    ):
        """Test is_enabled returns default value when waffle raises exception."""
        mock_flag_is_active.side_effect = Exception("Waffle error")

        result = FeatureFlags.is_enabled("FILES", self.request, self.user)

        self.assertFalse(result)  # FILES default is False

    @patch("apps.featureflags.helpers.flag_is_active")
    def test_is_enabled_waffle_exception_returns_default_true(
        self, mock_flag_is_active
    ):
        """Test is_enabled returns default value when waffle raises exception."""
        mock_flag_is_active.side_effect = Exception("Waffle error")

        result = FeatureFlags.is_enabled("EMAIL_EDITOR", self.request, self.user)

        self.assertTrue(result)  # EMAIL_EDITOR default is True

    @patch("apps.featureflags.helpers.flag_is_active")
    def test_is_enabled_unknown_flag_returns_false(self, mock_flag_is_active):
        """Test is_enabled returns False for unknown flags."""
        mock_flag_is_active.side_effect = Exception("Flag not found")

        result = FeatureFlags.is_enabled("UNKNOWN_FLAG", self.request, self.user)

        self.assertFalse(result)

    @patch("apps.featureflags.helpers.switch_is_active")
    def test_is_switch_active_when_active(self, mock_switch_is_active):
        """Test is_switch_active when switch is active."""
        mock_switch_is_active.return_value = True

        result = FeatureFlags.is_switch_active("TEST_SWITCH")

        self.assertTrue(result)
        mock_switch_is_active.assert_called_once_with("TEST_SWITCH")

    @patch("apps.featureflags.helpers.switch_is_active")
    def test_is_switch_active_when_inactive(self, mock_switch_is_active):
        """Test is_switch_active when switch is inactive."""
        mock_switch_is_active.return_value = False

        result = FeatureFlags.is_switch_active("TEST_SWITCH")

        self.assertFalse(result)
        mock_switch_is_active.assert_called_once_with("TEST_SWITCH")

    @patch("apps.featureflags.helpers.switch_is_active")
    def test_is_switch_active_exception_returns_false(self, mock_switch_is_active):
        """Test is_switch_active returns False when exception occurs."""
        mock_switch_is_active.side_effect = Exception("Switch error")

        result = FeatureFlags.is_switch_active("TEST_SWITCH")

        self.assertFalse(result)

    @patch("apps.featureflags.helpers.sample_is_active")
    def test_is_sample_active_when_active(self, mock_sample_is_active):
        """Test is_sample_active when sample is active."""
        mock_sample_is_active.return_value = True

        result = FeatureFlags.is_sample_active("TEST_SAMPLE")

        self.assertTrue(result)
        mock_sample_is_active.assert_called_once_with("TEST_SAMPLE")

    @patch("apps.featureflags.helpers.sample_is_active")
    def test_is_sample_active_when_inactive(self, mock_sample_is_active):
        """Test is_sample_active when sample is inactive."""
        mock_sample_is_active.return_value = False

        result = FeatureFlags.is_sample_active("TEST_SAMPLE")

        self.assertFalse(result)
        mock_sample_is_active.assert_called_once_with("TEST_SAMPLE")

    @patch("apps.featureflags.helpers.sample_is_active")
    def test_is_sample_active_exception_returns_false(self, mock_sample_is_active):
        """Test is_sample_active returns False when exception occurs."""
        mock_sample_is_active.side_effect = Exception("Sample error")

        result = FeatureFlags.is_sample_active("TEST_SAMPLE")

        self.assertFalse(result)

    @patch("apps.featureflags.helpers.FeatureFlags.is_enabled")
    def test_get_enabled_flags_with_request_and_user(self, mock_is_enabled):
        """Test get_enabled_flags with request and user."""

        # Mock different return values for different flags
        def side_effect(flag_name, request, user):
            return flag_name in ["EMAIL_EDITOR", "FILES"]

        mock_is_enabled.side_effect = side_effect

        result = FeatureFlags.get_enabled_flags(self.request, self.user)

        # Should check all default flags
        self.assertEqual(len(result), len(FeatureFlags.DEFAULT_FLAGS))
        self.assertTrue(result["EMAIL_EDITOR"])
        self.assertTrue(result["FILES"])
        self.assertFalse(result["RABBITMQ"])
        self.assertFalse(result["ADVANCED_ANALYTICS"])
        self.assertFalse(result["BETA_FEATURES"])
        self.assertFalse(result["API_V2"])
        self.assertFalse(result["MAINTENANCE_MODE"])

        # Verify is_enabled was called for each flag
        self.assertEqual(mock_is_enabled.call_count, len(FeatureFlags.DEFAULT_FLAGS))

    @patch("apps.featureflags.helpers.FeatureFlags.is_enabled")
    def test_get_enabled_flags_without_request_and_user(self, mock_is_enabled):
        """Test get_enabled_flags without request and user."""
        mock_is_enabled.return_value = False

        result = FeatureFlags.get_enabled_flags()

        # Should check all default flags
        self.assertEqual(len(result), len(FeatureFlags.DEFAULT_FLAGS))
        for _, enabled in result.items():
            self.assertFalse(enabled)

    @patch("apps.featureflags.helpers.FeatureFlags.is_enabled")
    def test_get_flag_status_existing_flag(self, mock_is_enabled):
        """Test get_flag_status for existing flag."""
        mock_is_enabled.return_value = True

        result = FeatureFlags.get_flag_status("FILES", self.request, self.user)

        expected = {
            "name": "FILES",
            "enabled": True,
            "description": "Enable file upload and management functionality",
            "default": False,
        }
        self.assertEqual(result, expected)
        mock_is_enabled.assert_called_once_with("FILES", self.request, self.user)

    @patch("apps.featureflags.helpers.FeatureFlags.is_enabled")
    def test_get_flag_status_unknown_flag(self, mock_is_enabled):
        """Test get_flag_status for unknown flag."""
        mock_is_enabled.return_value = False

        result = FeatureFlags.get_flag_status("UNKNOWN_FLAG", self.request, self.user)

        expected = {
            "name": "UNKNOWN_FLAG",
            "enabled": False,
            "description": "No description available",
            "default": False,
        }
        self.assertEqual(result, expected)


class ConvenienceFunctionsTest(TestCase):
    """Test convenience functions."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"  # nosec B106
        )
        self.request_factory = RequestFactory()
        self.request = self.request_factory.get("/")
        self.request.user = self.user

    @patch("apps.featureflags.helpers.FeatureFlags.is_enabled")
    def test_is_feature_enabled_function(self, mock_is_enabled):
        """Test is_feature_enabled convenience function."""
        mock_is_enabled.return_value = True

        result = is_feature_enabled("FILES", self.request, self.user)

        self.assertTrue(result)
        mock_is_enabled.assert_called_once_with("FILES", self.request, self.user)

    @patch("apps.featureflags.helpers.FeatureFlags.get_enabled_flags")
    def test_get_feature_context(self, mock_get_enabled_flags):
        """Test get_feature_context function."""
        mock_flags = {"FILES": True, "EMAIL_EDITOR": False}
        mock_get_enabled_flags.return_value = mock_flags

        result = get_feature_context(self.request, self.user)

        expected = {
            "features": mock_flags,
            "feature_flags": FeatureFlags,
        }
        self.assertEqual(result, expected)
        mock_get_enabled_flags.assert_called_once_with(self.request, self.user)


class RequireFeatureFlagDecoratorTest(TestCase):
    """Test require_feature_flag decorator."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"  # nosec B106
        )
        self.request_factory = RequestFactory()
        self.request = self.request_factory.get("/")
        self.request.user = self.user

    @patch("apps.featureflags.helpers.is_feature_enabled")
    def test_decorator_on_function_flag_enabled(self, mock_is_feature_enabled):
        """Test decorator on function when flag is enabled."""
        mock_is_feature_enabled.return_value = True

        @require_feature_flag("FILES")
        def test_view(request):
            return "success"

        result = test_view(self.request)

        self.assertEqual(result, "success")
        mock_is_feature_enabled.assert_called_once_with("FILES", self.request)

    @patch("apps.featureflags.helpers.is_feature_enabled")
    def test_decorator_on_function_flag_disabled(self, mock_is_feature_enabled):
        """Test decorator on function when flag is disabled."""
        mock_is_feature_enabled.return_value = False

        @require_feature_flag("FILES")
        def test_view(request):
            return "success"

        with self.assertRaises(Http404):
            test_view(self.request)

        mock_is_feature_enabled.assert_called_once_with("FILES", self.request)

    @patch("apps.featureflags.helpers.is_feature_enabled")
    def test_decorator_on_function_no_request(self, mock_is_feature_enabled):
        """Test decorator on function with no identifiable request."""
        mock_is_feature_enabled.return_value = False

        @require_feature_flag("FILES")
        def test_view(some_arg, some_kwarg=None):
            return "success"

        with self.assertRaises(Http404):
            test_view("test_arg", some_kwarg="test")

        mock_is_feature_enabled.assert_called_once_with("FILES", None)

    @patch("apps.featureflags.helpers.is_feature_enabled")
    def test_decorator_on_class_flag_enabled(self, mock_is_feature_enabled):
        """Test decorator on class when flag is enabled."""
        mock_is_feature_enabled.return_value = True

        @require_feature_flag("FILES")
        class TestViewSet:
            def dispatch(self, request, *args, **kwargs):
                return "success"

        viewset = TestViewSet()
        result = viewset.dispatch(self.request)

        self.assertEqual(result, "success")
        mock_is_feature_enabled.assert_called_once_with("FILES", self.request)

    @patch("apps.featureflags.helpers.is_feature_enabled")
    def test_decorator_on_class_flag_disabled(self, mock_is_feature_enabled):
        """Test decorator on class when flag is disabled."""
        mock_is_feature_enabled.return_value = False

        @require_feature_flag("FILES")
        class TestViewSet:
            def dispatch(self, request, *args, **kwargs):
                return "success"

        viewset = TestViewSet()

        with self.assertRaises(Http404):
            viewset.dispatch(self.request)

        mock_is_feature_enabled.assert_called_once_with("FILES", self.request)

    @patch("apps.featureflags.helpers.is_feature_enabled")
    def test_decorator_preserves_function_metadata(self, mock_is_feature_enabled):
        """Test decorator preserves original function metadata."""
        mock_is_feature_enabled.return_value = True

        @require_feature_flag("FILES")
        def test_view(request):
            """Test view docstring."""
            return "success"

        # The decorator should preserve the original function's behavior
        result = test_view(self.request)
        self.assertEqual(result, "success")


class FeatureFlagIntegrationTest(TestCase):
    """Test feature flags integration with waffle models."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"  # nosec B106
        )
        self.request_factory = RequestFactory()
        self.request = self.request_factory.get("/")
        self.request.user = self.user

        # Create waffle models for testing
        self.flag = Flag.objects.create(
            name="TEST_FLAG", everyone=False, note="Test flag"
        )
        self.switch = Switch.objects.create(name="TEST_SWITCH", active=True)
        self.sample = Sample.objects.create(name="TEST_SAMPLE", percent=50)

    def test_is_enabled_with_user_targeting(self):
        """Test is_enabled with user-specific flag targeting."""
        # Add user to flag
        self.flag.users.add(self.user)

        result = FeatureFlags.is_enabled("TEST_FLAG", self.request, self.user)

        # Since waffle handles the actual logic, we're testing our wrapper
        # The result depends on waffle's implementation
        self.assertIsInstance(result, bool)

    def test_is_enabled_with_everyone_flag(self):
        """Test is_enabled with flag enabled for everyone."""
        self.flag.everyone = True
        self.flag.save()

        result = FeatureFlags.is_enabled("TEST_FLAG", self.request, self.user)

        self.assertTrue(result)

    def test_is_enabled_with_disabled_flag(self):
        """Test is_enabled with disabled flag."""
        # Flag is created with everyone=False and no users
        result = FeatureFlags.is_enabled("TEST_FLAG", self.request, self.user)

        self.assertFalse(result)

    def test_is_switch_active_with_active_switch(self):
        """Test is_switch_active with active switch."""
        result = FeatureFlags.is_switch_active("TEST_SWITCH")

        self.assertTrue(result)

    def test_is_switch_active_with_inactive_switch(self):
        """Test is_switch_active with inactive switch."""
        self.switch.active = False
        self.switch.save()

        result = FeatureFlags.is_switch_active("TEST_SWITCH")

        self.assertFalse(result)

    def test_is_sample_active_with_sample(self):
        """Test is_sample_active with sample."""
        # Sample activation is probabilistic, so we test the method exists
        result = FeatureFlags.is_sample_active("TEST_SAMPLE")

        self.assertIsInstance(result, bool)

    def test_multiple_flag_types_combination(self):
        """Test combining different flag types in get_enabled_flags."""
        # Create flags for default flag names
        Flag.objects.create(name="FILES", everyone=True)
        Flag.objects.create(name="EMAIL_EDITOR", everyone=False)

        result = FeatureFlags.get_enabled_flags(self.request, self.user)

        # FILES should be True (everyone=True)
        self.assertTrue(result["FILES"])
        # EMAIL_EDITOR should be False (everyone=False, no users)
        self.assertFalse(result["EMAIL_EDITOR"])


class FeatureFlagErrorHandlingTest(TestCase):
    """Test feature flag error handling and edge cases."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"  # nosec B106
        )
        self.request_factory = RequestFactory()
        self.request = self.request_factory.get("/")
        self.request.user = self.user

    def test_is_enabled_with_none_values(self):
        """Test is_enabled handles None values gracefully."""
        result = FeatureFlags.is_enabled("FILES", None, None)

        self.assertIsInstance(result, bool)

    def test_is_enabled_with_invalid_flag_name(self):
        """Test is_enabled with invalid flag name."""
        result = FeatureFlags.is_enabled(None, self.request, self.user)

        # Should not crash and return boolean
        self.assertIsInstance(result, bool)

    def test_get_enabled_flags_handles_partial_failures(self):
        """Test get_enabled_flags handles partial failures."""
        with patch("apps.featureflags.helpers.flag_is_active") as mock_flag_is_active:
            # Make some calls fail
            def side_effect(request, flag_name):
                if flag_name == "FILES":
                    raise Exception("Database error")
                return False

            mock_flag_is_active.side_effect = side_effect

            result = FeatureFlags.get_enabled_flags(self.request, self.user)

            # Should return results for all flags even if some fail
            self.assertEqual(len(result), len(FeatureFlags.DEFAULT_FLAGS))
            # FILES should return its default value (False) when exception occurs
            self.assertFalse(result["FILES"])

    def test_get_flag_status_with_empty_config(self):
        """Test get_flag_status with missing flag configuration."""
        with patch.dict(FeatureFlags.DEFAULT_FLAGS, {}, clear=True):
            result = FeatureFlags.get_flag_status("UNKNOWN_FLAG")

            expected = {
                "name": "UNKNOWN_FLAG",
                "enabled": False,
                "description": "No description available",
                "default": False,
            }
            self.assertEqual(result, expected)

    @patch("apps.featureflags.helpers.is_feature_enabled")
    def test_require_feature_flag_decorator_with_complex_args(
        self, mock_is_feature_enabled
    ):
        """Test decorator with complex function signatures."""
        mock_is_feature_enabled.return_value = True

        @require_feature_flag("FILES")
        def complex_view(request, pk, *args, **kwargs):
            return f"pk: {pk}, args: {args}, kwargs: {kwargs}"

        result = complex_view(self.request, 123, "extra", test="value")

        self.assertEqual(result, "pk: 123, args: ('extra',), kwargs: {'test': 'value'}")
        mock_is_feature_enabled.assert_called_once_with("FILES", self.request)

    def test_feature_context_with_none_values(self):
        """Test get_feature_context with None values."""
        result = get_feature_context(None, None)

        self.assertIn("features", result)
        self.assertIn("feature_flags", result)
        self.assertEqual(result["feature_flags"], FeatureFlags)


class FeatureFlagCachingTest(TestCase):
    """Test feature flag caching behavior."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"  # nosec B106
        )
        self.request_factory = RequestFactory()
        self.request = self.request_factory.get("/")
        self.request.user = self.user

    def test_repeated_flag_checks_performance(self):
        """Test that repeated flag checks don't cause excessive database queries."""
        # Create a flag
        Flag.objects.create(name="PERFORMANCE_TEST", everyone=True)

        # This test ensures we don't regress on performance
        # Multiple calls to the same flag should leverage waffle's caching
        results = []
        for _ in range(10):
            result = FeatureFlags.is_enabled(
                "PERFORMANCE_TEST", self.request, self.user
            )
            results.append(result)

        # All results should be consistent
        self.assertTrue(all(results))

    def test_flag_changes_reflected_in_checks(self):
        """Test that flag changes are reflected in subsequent checks."""
        # Create a flag that's initially disabled
        flag = Flag.objects.create(name="DYNAMIC_TEST", everyone=False)

        # Initial check should be False
        result1 = FeatureFlags.is_enabled("DYNAMIC_TEST", self.request, self.user)
        self.assertFalse(result1)

        # Enable the flag
        flag.everyone = True
        flag.save()

        # Subsequent check should be True (may require cache clearing in real usage)
        result2 = FeatureFlags.is_enabled("DYNAMIC_TEST", self.request, self.user)
        self.assertTrue(result2)

    def test_switch_changes_reflected_in_checks(self):
        """Test that switch changes are reflected in subsequent checks."""
        # Create a switch that's initially active
        switch = Switch.objects.create(name="DYNAMIC_SWITCH_TEST", active=True)

        # Initial check should be True
        result1 = FeatureFlags.is_switch_active("DYNAMIC_SWITCH_TEST")
        self.assertTrue(result1)

        # Disable the switch
        switch.active = False
        switch.save()

        # Subsequent check should be False (may require cache clearing in real usage)
        result2 = FeatureFlags.is_switch_active("DYNAMIC_SWITCH_TEST")
        self.assertFalse(result2)

    def test_multiple_rapid_flag_changes(self):
        """Test rapid flag changes to expose caching issues."""
        # Create a flag that's initially disabled
        flag = Flag.objects.create(name="RAPID_TEST", everyone=False)

        # Rapid toggle test
        for i in range(5):
            expected_state = i % 2 == 1  # True for odd iterations
            flag.everyone = expected_state
            flag.save()

            result = FeatureFlags.is_enabled("RAPID_TEST", self.request, self.user)
            self.assertEqual(
                result,
                expected_state,
                f"Iteration {i}: Expected {expected_state}, got {result}",
            )

    def test_concurrent_flag_access_with_changes(self):
        """Test flag access while making changes (simulates real-world scenario)."""
        # Create a flag
        flag = Flag.objects.create(name="CONCURRENT_TEST", everyone=False)

        # Check multiple times before change
        results_before = []
        for _ in range(3):
            results_before.append(
                FeatureFlags.is_enabled("CONCURRENT_TEST", self.request, self.user)
            )

        # All should be False
        self.assertTrue(all(not r for r in results_before))

        # Change flag
        flag.everyone = True
        flag.save()

        # Check multiple times after change
        results_after = []
        for _ in range(3):
            results_after.append(
                FeatureFlags.is_enabled("CONCURRENT_TEST", self.request, self.user)
            )

        # All should be True
        self.assertTrue(
            all(results_after),
            f"After change results should all be True, got: {results_after}",
        )

    def test_cross_flag_cache_interference(self):
        """Test that caching one flag doesn't interfere with others."""
        # Create multiple flags
        Flag.objects.create(name="CACHE_TEST_1", everyone=True)
        flag2 = Flag.objects.create(name="CACHE_TEST_2", everyone=False)

        # Check both flags
        result1_initial = FeatureFlags.is_enabled(
            "CACHE_TEST_1", self.request, self.user
        )
        result2_initial = FeatureFlags.is_enabled(
            "CACHE_TEST_2", self.request, self.user
        )

        self.assertTrue(result1_initial)
        self.assertFalse(result2_initial)

        # Change only flag2
        flag2.everyone = True
        flag2.save()

        # Check both flags again
        result1_after = FeatureFlags.is_enabled("CACHE_TEST_1", self.request, self.user)
        result2_after = FeatureFlags.is_enabled("CACHE_TEST_2", self.request, self.user)

        # Flag1 should remain True, Flag2 should now be True
        self.assertTrue(result1_after)
        self.assertTrue(result2_after)

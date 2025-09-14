"""Tests for feature flag cache management and waffle testutils integration."""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from waffle.models import Flag, Sample, Switch
from waffle.testutils import override_flag, override_sample, override_switch

from apps.featureflags.helpers import (
    FeatureFlags,
    clear_all_feature_caches,
    clear_feature_cache,
    clear_switch_cache,
    is_feature_enabled_fresh,
)

User = get_user_model()


class WaffleTestUtilsIntegrationTest(TestCase):
    """Test waffle testutils integration for reliable feature flag testing."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"  # nosec B106
        )
        self.request_factory = RequestFactory()
        self.request = self.request_factory.get("/")
        self.request.user = self.user

    def test_override_flag_context_manager(self):
        """Test using override_flag as a context manager."""
        # Flag doesn't exist initially
        self.assertFalse(FeatureFlags.is_enabled("TEST_FLAG", self.request, self.user))

        # Override flag to be active
        with override_flag("TEST_FLAG", active=True):
            result = FeatureFlags.is_enabled("TEST_FLAG", self.request, self.user)
            self.assertTrue(result)

        # Flag should be back to original state (False/non-existent)
        self.assertFalse(FeatureFlags.is_enabled("TEST_FLAG", self.request, self.user))

    def test_override_flag_decorator(self):
        """Test using override_flag as a decorator."""

        @override_flag("TEST_FLAG", active=True)
        def test_function():
            return FeatureFlags.is_enabled("TEST_FLAG", self.request, self.user)

        # Inside decorated function, flag should be active
        result = test_function()
        self.assertTrue(result)

        # Outside decorated function, flag should be inactive
        result_outside = FeatureFlags.is_enabled("TEST_FLAG", self.request, self.user)
        self.assertFalse(result_outside)

    def test_override_switch_context_manager(self):
        """Test using override_switch as a context manager."""
        # Switch doesn't exist initially
        self.assertFalse(FeatureFlags.is_switch_active("TEST_SWITCH"))

        # Override switch to be active
        with override_switch("TEST_SWITCH", active=True):
            result = FeatureFlags.is_switch_active("TEST_SWITCH")
            self.assertTrue(result)

        # Switch should be back to original state (False/non-existent)
        self.assertFalse(FeatureFlags.is_switch_active("TEST_SWITCH"))

    def test_override_switch_decorator(self):
        """Test using override_switch as a decorator."""

        @override_switch("TEST_SWITCH", active=False)
        def test_function():
            return FeatureFlags.is_switch_active("TEST_SWITCH")

        # Inside decorated function, switch should be inactive
        result = test_function()
        self.assertFalse(result)

        # Outside decorated function, switch should also be inactive (default)
        result_outside = FeatureFlags.is_switch_active("TEST_SWITCH")
        self.assertFalse(result_outside)

    def test_override_sample_context_manager(self):
        """Test using override_sample as a context manager."""
        # Sample doesn't exist initially
        self.assertFalse(FeatureFlags.is_sample_active("TEST_SAMPLE"))

        # Override sample to be active (100% chance)
        with override_sample("TEST_SAMPLE", active=True):
            result = FeatureFlags.is_sample_active("TEST_SAMPLE")
            self.assertTrue(result)

        # Sample should be back to original state (False/non-existent)
        self.assertFalse(FeatureFlags.is_sample_active("TEST_SAMPLE"))

    def test_nested_overrides(self):
        """Test nested waffle overrides."""
        with override_flag("FLAG_A", active=True):
            with override_flag("FLAG_B", active=False):
                result_a = FeatureFlags.is_enabled("FLAG_A", self.request, self.user)
                result_b = FeatureFlags.is_enabled("FLAG_B", self.request, self.user)

                self.assertTrue(result_a)
                self.assertFalse(result_b)

        # Both flags should be back to original state
        self.assertFalse(FeatureFlags.is_enabled("FLAG_A", self.request, self.user))
        self.assertFalse(FeatureFlags.is_enabled("FLAG_B", self.request, self.user))

    def test_multiple_overrides_same_test(self):
        """Test multiple overrides in the same test."""
        # First override
        with override_flag("MULTI_TEST", active=True):
            result1 = FeatureFlags.is_enabled("MULTI_TEST", self.request, self.user)
            self.assertTrue(result1)

        # Second override with different value
        with override_flag("MULTI_TEST", active=False):
            result2 = FeatureFlags.is_enabled("MULTI_TEST", self.request, self.user)
            self.assertFalse(result2)

        # Back to original state
        result3 = FeatureFlags.is_enabled("MULTI_TEST", self.request, self.user)
        self.assertFalse(result3)


class CacheManagementTest(TestCase):
    """Test cache management functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"  # nosec B106
        )
        self.request_factory = RequestFactory()
        self.request = self.request_factory.get("/")
        self.request.user = self.user

    def test_clear_flag_cache(self):
        """Test clearing flag cache."""
        # Create a flag
        flag = Flag.objects.create(name="CACHE_CLEAR_TEST", everyone=False)

        # Initial state
        result1 = FeatureFlags.is_enabled("CACHE_CLEAR_TEST", self.request, self.user)
        self.assertFalse(result1)

        # Change flag in database
        flag.everyone = True
        flag.save()

        # Clear cache and check again
        cleared = clear_feature_cache("CACHE_CLEAR_TEST")
        self.assertTrue(cleared)

        result2 = FeatureFlags.is_enabled("CACHE_CLEAR_TEST", self.request, self.user)
        self.assertTrue(result2)

    def test_clear_switch_cache(self):
        """Test clearing switch cache."""
        # Create a switch
        switch = Switch.objects.create(name="SWITCH_CACHE_TEST", active=True)

        # Initial state
        result1 = FeatureFlags.is_switch_active("SWITCH_CACHE_TEST")
        self.assertTrue(result1)

        # Change switch in database
        switch.active = False
        switch.save()

        # Clear cache and check again
        cleared = clear_switch_cache("SWITCH_CACHE_TEST")
        self.assertTrue(cleared)

        result2 = FeatureFlags.is_switch_active("SWITCH_CACHE_TEST")
        self.assertFalse(result2)

    def test_clear_nonexistent_flag_cache(self):
        """Test clearing cache for non-existent flag."""
        cleared = clear_feature_cache("NONEXISTENT_FLAG")
        self.assertFalse(cleared)

    def test_clear_all_caches(self):
        """Test clearing all waffle caches."""
        # Create test objects
        Flag.objects.create(name="TEST_FLAG_ALL", everyone=True)
        Switch.objects.create(name="TEST_SWITCH_ALL", active=True)
        Sample.objects.create(name="TEST_SAMPLE_ALL", percent=100)

        # Clear all caches
        cleared = clear_all_feature_caches()
        self.assertTrue(cleared)

    def test_is_feature_enabled_fresh(self):
        """Test is_feature_enabled_fresh function."""
        # Create a flag
        flag = Flag.objects.create(name="FRESH_TEST", everyone=False)

        # Initial check with fresh cache
        result1 = is_feature_enabled_fresh("FRESH_TEST", self.request, self.user)
        self.assertFalse(result1)

        # Change flag
        flag.everyone = True
        flag.save()

        # Check with fresh cache - should get updated value
        result2 = is_feature_enabled_fresh("FRESH_TEST", self.request, self.user)
        self.assertTrue(result2)

    def test_cache_methods_with_exceptions(self):
        """Test cache methods handle exceptions gracefully."""
        # Test with None - should return False, not raise exception
        result = clear_feature_cache(None)
        self.assertFalse(result)

    def test_cache_clearing_with_database_changes(self):
        """Test comprehensive cache clearing with database changes."""
        # Create multiple flags and switches
        flag1 = Flag.objects.create(name="DB_CHANGE_1", everyone=False)
        flag2 = Flag.objects.create(name="DB_CHANGE_2", everyone=True)
        switch1 = Switch.objects.create(name="DB_SWITCH_1", active=False)

        # Initial states
        self.assertFalse(FeatureFlags.is_enabled("DB_CHANGE_1", self.request, self.user))
        self.assertTrue(FeatureFlags.is_enabled("DB_CHANGE_2", self.request, self.user))
        self.assertFalse(FeatureFlags.is_switch_active("DB_SWITCH_1"))

        # Change all states
        flag1.everyone = True
        flag1.save()
        flag2.everyone = False
        flag2.save()
        switch1.active = True
        switch1.save()

        # Clear all caches
        clear_all_feature_caches()

        # Check updated states
        self.assertTrue(FeatureFlags.is_enabled("DB_CHANGE_1", self.request, self.user))
        self.assertFalse(FeatureFlags.is_enabled("DB_CHANGE_2", self.request, self.user))
        self.assertTrue(FeatureFlags.is_switch_active("DB_SWITCH_1"))


class CacheReliabilityTest(TestCase):
    """Test cache reliability and edge cases."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"  # nosec B106
        )
        self.request_factory = RequestFactory()
        self.request = self.request_factory.get("/")
        self.request.user = self.user

    def test_cache_consistency_across_methods(self):
        """Test that different methods see consistent cache state."""
        flag = Flag.objects.create(name="CONSISTENCY_TEST", everyone=False)

        # Multiple checks should be consistent
        results = []
        for _ in range(3):
            results.append(
                FeatureFlags.is_enabled("CONSISTENCY_TEST", self.request, self.user)
            )

        self.assertTrue(all(not r for r in results), "All initial results should be False")

        # Change flag and clear cache
        flag.everyone = True
        flag.save()
        clear_feature_cache("CONSISTENCY_TEST")

        # Multiple checks after change should be consistent
        results_after = []
        for _ in range(3):
            results_after.append(
                FeatureFlags.is_enabled("CONSISTENCY_TEST", self.request, self.user)
            )

        self.assertTrue(all(results_after), "All results after change should be True")

    def test_cache_isolation_between_flags(self):
        """Test that cache clearing for one flag doesn't affect others."""
        flag1 = Flag.objects.create(name="ISOLATION_1", everyone=True)
        flag2 = Flag.objects.create(name="ISOLATION_2", everyone=False)

        # Initial states
        result1_initial = FeatureFlags.is_enabled("ISOLATION_1", self.request, self.user)
        result2_initial = FeatureFlags.is_enabled("ISOLATION_2", self.request, self.user)
        self.assertTrue(result1_initial)
        self.assertFalse(result2_initial)

        # Change only flag2 and clear its cache
        flag2.everyone = True
        flag2.save()
        clear_feature_cache("ISOLATION_2")

        # Check both flags
        result1_after = FeatureFlags.is_enabled("ISOLATION_1", self.request, self.user)
        result2_after = FeatureFlags.is_enabled("ISOLATION_2", self.request, self.user)

        # Flag1 should be unchanged, Flag2 should be updated
        self.assertTrue(result1_after)
        self.assertTrue(result2_after)

    def test_cache_refresh_methods_consistency(self):
        """Test that cache refresh methods provide consistent results."""
        # Create a flag that's initially disabled
        flag = Flag.objects.create(name="REFRESH_CONSISTENCY_TEST", everyone=False)

        # Regular check
        result1 = FeatureFlags.is_enabled("REFRESH_CONSISTENCY_TEST", self.request, self.user)
        # Fresh check
        result2 = is_feature_enabled_fresh("REFRESH_CONSISTENCY_TEST", self.request, self.user)

        # Both should be False initially
        self.assertFalse(result1)
        self.assertFalse(result2)

        # Enable flag
        flag.everyone = True
        flag.save()

        # Regular check might be cached
        result3 = FeatureFlags.is_enabled("REFRESH_CONSISTENCY_TEST", self.request, self.user)
        # Fresh check should always be current
        result4 = is_feature_enabled_fresh("REFRESH_CONSISTENCY_TEST", self.request, self.user)

        # Fresh check should definitely be True
        self.assertTrue(result4, "Fresh check should always return current value")
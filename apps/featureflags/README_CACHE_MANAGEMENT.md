# Feature Flag Cache Management

This document explains the caching issues with Django Waffle and how to use the enhanced cache management features in this Django SaaS boilerplate.

## Problem: Waffle Caching Issues

Django Waffle aggressively caches feature flags, switches, and samples to improve performance. However, this can cause issues when:

1. **Flag changes don't reflect immediately**: When you change a flag in the database, cached values may persist
2. **Test reliability**: Tests that modify flags during execution may see stale cached values
3. **Development inconsistencies**: Flag changes made in admin or management commands may not be visible immediately

## Solutions Implemented

### 1. Cache Clearing Utilities

The `FeatureFlags` helper class now includes methods to manually clear waffle caches:

```python
from apps.featureflags.helpers import FeatureFlags

# Clear cache for a specific flag
FeatureFlags.clear_flag_cache("MY_FLAG")

# Clear cache for a specific switch
FeatureFlags.clear_switch_cache("MY_SWITCH")

# Clear cache for a specific sample
FeatureFlags.clear_sample_cache("MY_SAMPLE")

# Clear all waffle caches
FeatureFlags.clear_all_waffle_cache()
```

### 2. Fresh Check Methods

Use these methods when you need the most up-to-date flag status:

```python
from apps.featureflags.helpers import FeatureFlags

# Regular check (may use cached value)
is_enabled = FeatureFlags.is_enabled("MY_FLAG", request, user)

# Fresh check (clears cache first)
is_enabled = FeatureFlags.is_enabled_with_cache_refresh("MY_FLAG", request, user)

# Fresh switch check
is_active = FeatureFlags.is_switch_active_with_cache_refresh("MY_SWITCH")
```

### 3. Convenience Functions

Shorter function names for common operations:

```python
from apps.featureflags.helpers import (
    clear_feature_cache,
    clear_switch_cache,
    clear_all_feature_caches,
    is_feature_enabled_fresh,
)

# Clear specific flag cache
clear_feature_cache("MY_FLAG")

# Check flag with fresh data
if is_feature_enabled_fresh("MY_FLAG", request, user):
    # Feature is enabled
    pass
```

## Testing with Waffle

### Using Waffle TestUtils (Recommended)

For reliable testing, use waffle's built-in test utilities:

```python
from waffle.testutils import override_flag, override_switch, override_sample

class MyTestCase(TestCase):
    def test_with_flag_enabled(self):
        with override_flag("MY_FLAG", active=True):
            # Test code here - flag is guaranteed to be active
            result = FeatureFlags.is_enabled("MY_FLAG", request, user)
            self.assertTrue(result)
        # Flag is restored to original state

    @override_flag("MY_FLAG", active=False)
    def test_with_flag_disabled(self):
        # Test code here - flag is guaranteed to be inactive
        result = FeatureFlags.is_enabled("MY_FLAG", request, user)
        self.assertFalse(result)
```

### Manual Cache Management in Tests

When you need to test dynamic flag changes:

```python
from apps.featureflags.helpers import clear_feature_cache, is_feature_enabled_fresh

class MyTestCase(TestCase):
    def test_flag_change_detection(self):
        # Create a flag
        flag = Flag.objects.create(name="DYNAMIC_FLAG", everyone=False)

        # Initial check
        result1 = FeatureFlags.is_enabled("DYNAMIC_FLAG", request, user)
        self.assertFalse(result1)

        # Change flag
        flag.everyone = True
        flag.save()

        # Use fresh check to ensure we see the change
        result2 = is_feature_enabled_fresh("DYNAMIC_FLAG", request, user)
        self.assertTrue(result2)
```

## Configuration

### Test Settings

The test configuration includes optimized waffle settings:

```python
# apps/config/settings/test.py

# Disable waffle caching for tests
WAFFLE_MAX_AGE = 0

# Use test-specific cache prefix
WAFFLE_CACHE_PREFIX = "waffle-test:"

# Don't auto-create missing flags
WAFFLE_CREATE_MISSING_FLAGS = False
WAFFLE_CREATE_MISSING_SWITCHES = False
WAFFLE_CREATE_MISSING_SAMPLES = False

# Use dummy cache backend
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}
```

### Production Settings

In production, waffle caching is enabled for performance:

```python
# apps/config/settings/base.py

# Use Redis for caching
CACHES = {"default": env.cache("REDIS_URL", default="redis://localhost:6379/0")}
```

## Best Practices

### 1. Use TestUtils for Testing

Always prefer waffle's `override_*` utilities for tests:

```python
# ✅ Good
with override_flag("MY_FLAG", active=True):
    test_feature()

# ❌ Avoid
flag = Flag.objects.create(name="MY_FLAG", everyone=True)
# ... test code
# Manual cleanup required
```

### 2. Clear Cache After Database Changes

When modifying flags outside of waffle's normal flow:

```python
# After direct database modification
flag.everyone = True
flag.save()
clear_feature_cache("MY_FLAG")  # Ensure cache is updated
```

### 3. Use Fresh Methods When Needed

Use fresh methods when you need real-time data:

```python
# In management commands or admin actions
if is_feature_enabled_fresh("MAINTENANCE_MODE"):
    # Check real-time status
    perform_maintenance()
```

### 4. Production Cache Management

In production, consider implementing cache invalidation in your flag management interfaces:

```python
class FlagAdminView:
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Clear cache when flag is modified via admin
        clear_feature_cache(obj.name)
```

## Troubleshooting

### Flags Not Updating

If flag changes aren't reflected:

1. Check if you're using the right cache backend
2. Clear the specific flag cache: `clear_feature_cache("FLAG_NAME")`
3. Use fresh methods: `is_feature_enabled_fresh("FLAG_NAME")`
4. Verify waffle configuration: `WAFFLE_MAX_AGE`, `WAFFLE_CACHE`

### Test Failures

If tests are failing due to cached values:

1. Use waffle testutils: `@override_flag("FLAG", active=True)`
2. Clear cache manually: `clear_feature_cache("FLAG")`
3. Check test settings for `WAFFLE_MAX_AGE = 0`

### Performance Issues

If cache clearing is impacting performance:

1. Only clear specific caches, not all: `clear_feature_cache("FLAG")` vs `clear_all_feature_caches()`
2. Consider implementing smarter cache invalidation
3. Profile your application to identify cache clearing hotspots

## API Reference

### Class Methods

- `FeatureFlags.clear_flag_cache(flag_name: str) -> bool`
- `FeatureFlags.clear_switch_cache(switch_name: str) -> bool`
- `FeatureFlags.clear_sample_cache(sample_name: str) -> bool`
- `FeatureFlags.clear_all_waffle_cache() -> bool`
- `FeatureFlags.is_enabled_with_cache_refresh(flag_name, request=None, user=None) -> bool`
- `FeatureFlags.is_switch_active_with_cache_refresh(switch_name: str) -> bool`

### Convenience Functions

- `clear_feature_cache(flag_name: str) -> bool`
- `clear_switch_cache(switch_name: str) -> bool`
- `clear_all_feature_caches() -> bool`
- `is_feature_enabled_fresh(flag_name, request=None, user=None) -> bool`

All cache clearing methods return `True` on success, `False` on failure.
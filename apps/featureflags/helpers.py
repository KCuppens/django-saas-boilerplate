"""Feature flag helper functions and classes."""

from typing import TYPE_CHECKING, Optional

from django.contrib.auth import get_user_model
from django.core.cache import cache

from waffle import flag_is_active, sample_is_active, switch_is_active
from waffle.models import Flag, Sample, Switch

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser as User
else:
    User = get_user_model()


class FeatureFlags:
    """Helper class for feature flag operations."""

    # Default flags configuration
    DEFAULT_FLAGS = {
        "FILES": {
            "description": "Enable file upload and management functionality",
            "default": False,
        },
        "EMAIL_EDITOR": {
            "description": "Enable email template editor in admin",
            "default": True,
        },
        "RABBITMQ": {
            "description": "Use RabbitMQ instead of Redis for Celery",
            "default": False,
        },
        "ADVANCED_ANALYTICS": {
            "description": "Enable advanced analytics and reporting",
            "default": False,
        },
        "BETA_FEATURES": {
            "description": "Enable beta features for testing",
            "default": False,
        },
        "API_V2": {
            "description": "Enable API version 2 endpoints",
            "default": False,
        },
        "MAINTENANCE_MODE": {
            "description": "Enable maintenance mode",
            "default": False,
        },
    }

    @classmethod
    def is_enabled(
        cls, flag_name: str, request=None, user: Optional[User] = None
    ) -> bool:
        """
        Check if a feature flag is enabled.

        Args:
            flag_name: Name of the flag
            request: Django request object (optional)
            user: User object (optional)

        Returns:
            bool: True if flag is active, False otherwise
        """
        try:
            return (
                flag_is_active(request, flag_name)
                if request
                else flag_is_active(None, flag_name)
            )
        except Exception:
            # Return default value if flag doesn't exist
            return cls.DEFAULT_FLAGS.get(flag_name, {}).get("default", False)

    @classmethod
    def is_switch_active(cls, switch_name: str) -> bool:
        """
        Check if a feature switch is active.

        Args:
            switch_name: Name of the switch

        Returns:
            bool: True if switch is active, False otherwise
        """
        try:
            return switch_is_active(switch_name)
        except Exception:
            return False

    @classmethod
    def is_sample_active(cls, sample_name: str) -> bool:
        """
        Check if a feature sample is active.

        Args:
            sample_name: Name of the sample

        Returns:
            bool: True if sample is active, False otherwise
        """
        try:
            return sample_is_active(sample_name)
        except Exception:
            return False

    @classmethod
    def get_enabled_flags(cls, request=None, user: Optional[User] = None) -> dict:
        """
        Get all enabled flags.

        Args:
            request: Django request object (optional)
            user: User object (optional)

        Returns:
            dict: Dictionary of flag names and their status
        """
        enabled_flags = {}
        for flag_name in cls.DEFAULT_FLAGS.keys():
            enabled_flags[flag_name] = cls.is_enabled(flag_name, request, user)
        return enabled_flags

    @classmethod
    def get_flag_status(
        cls, flag_name: str, request=None, user: Optional[User] = None
    ) -> dict:
        """
        Get detailed status of a feature flag.

        Args:
            flag_name: Name of the flag
            request: Django request object (optional)
            user: User object (optional)

        Returns:
            dict: Dictionary with flag status and metadata
        """
        flag_config = cls.DEFAULT_FLAGS.get(flag_name, {})

        return {
            "name": flag_name,
            "enabled": cls.is_enabled(flag_name, request, user),
            "description": flag_config.get("description", "No description available"),
            "default": flag_config.get("default", False),
        }

    @classmethod
    def clear_flag_cache(cls, flag_name: str) -> bool:
        """
        Clear cache for a specific flag.

        Args:
            flag_name: Name of the flag to clear cache for

        Returns:
            bool: True if cache was cleared successfully, False otherwise
        """
        try:
            flag = Flag.objects.filter(name=flag_name).first()
            if flag:
                flag.flush()
                return True
            return False
        except Exception:
            return False

    @classmethod
    def clear_switch_cache(cls, switch_name: str) -> bool:
        """
        Clear cache for a specific switch.

        Args:
            switch_name: Name of the switch to clear cache for

        Returns:
            bool: True if cache was cleared successfully, False otherwise
        """
        try:
            switch = Switch.objects.filter(name=switch_name).first()
            if switch:
                switch.flush()
                return True
            return False
        except Exception:
            return False

    @classmethod
    def clear_sample_cache(cls, sample_name: str) -> bool:
        """
        Clear cache for a specific sample.

        Args:
            sample_name: Name of the sample to clear cache for

        Returns:
            bool: True if cache was cleared successfully, False otherwise
        """
        try:
            sample = Sample.objects.filter(name=sample_name).first()
            if sample:
                sample.flush()
                return True
            return False
        except Exception:
            return False

    @classmethod
    def clear_all_waffle_cache(cls) -> bool:
        """
        Clear all waffle caches (flags, switches, and samples).

        Returns:
            bool: True if all caches were cleared successfully, False otherwise
        """
        try:
            success = True

            # Clear all flags
            for flag in Flag.objects.all():
                flag.flush()

            # Clear all switches
            for switch in Switch.objects.all():
                switch.flush()

            # Clear all samples
            for sample in Sample.objects.all():
                sample.flush()

            return success
        except Exception:
            return False

    @classmethod
    def is_enabled_with_cache_refresh(
        cls, flag_name: str, request=None, user: Optional[User] = None
    ) -> bool:
        """
        Check if a feature flag is enabled, with cache refresh.

        This method clears the flag cache before checking, ensuring fresh data.
        Use this when you need to ensure the most up-to-date flag status.

        Args:
            flag_name: Name of the flag
            request: Django request object (optional)
            user: User object (optional)

        Returns:
            bool: True if flag is active, False otherwise
        """
        cls.clear_flag_cache(flag_name)
        return cls.is_enabled(flag_name, request, user)

    @classmethod
    def is_switch_active_with_cache_refresh(cls, switch_name: str) -> bool:
        """
        Check if a feature switch is active, with cache refresh.

        This method clears the switch cache before checking, ensuring fresh data.
        Use this when you need to ensure the most up-to-date switch status.

        Args:
            switch_name: Name of the switch

        Returns:
            bool: True if switch is active, False otherwise
        """
        cls.clear_switch_cache(switch_name)
        return cls.is_switch_active(switch_name)


# Convenience functions
def is_feature_enabled(
    flag_name: str, request=None, user: Optional[User] = None
) -> bool:
    """Check if a feature flag is enabled."""
    return FeatureFlags.is_enabled(flag_name, request, user)


def is_feature_enabled_fresh(
    flag_name: str, request=None, user: Optional[User] = None
) -> bool:
    """Check if a feature flag is enabled with cache refresh."""
    return FeatureFlags.is_enabled_with_cache_refresh(flag_name, request, user)


def clear_feature_cache(flag_name: str) -> bool:
    """Clear cache for a specific feature flag."""
    return FeatureFlags.clear_flag_cache(flag_name)


def clear_switch_cache(switch_name: str) -> bool:
    """Clear cache for a specific switch."""
    return FeatureFlags.clear_switch_cache(switch_name)


def clear_all_feature_caches() -> bool:
    """Clear all waffle caches."""
    return FeatureFlags.clear_all_waffle_cache()


def require_feature_flag(flag_name: str):
    """Require a feature flag to be enabled."""

    def decorator(func_or_class):
        if isinstance(func_or_class, type):
            # Decorating a class (ViewSet)
            original_dispatch = func_or_class.dispatch

            def dispatch(self, request, *args, **kwargs):
                if not is_feature_enabled(flag_name, request):
                    from django.http import Http404

                    raise Http404("Feature not available")
                return original_dispatch(self, request, *args, **kwargs)

            func_or_class.dispatch = dispatch
            return func_or_class
        else:
            # Decorating a function
            def wrapper(*args, **kwargs):
                # Try to get request from args/kwargs
                request = None
                for arg in args:
                    if hasattr(arg, "user") and hasattr(arg, "META"):
                        request = arg
                        break

                if not is_feature_enabled(flag_name, request):
                    from django.http import Http404

                    raise Http404("Feature not available")

                return func_or_class(*args, **kwargs)

            return wrapper

    return decorator


def get_feature_context(request=None, user: Optional[User] = None) -> dict:
    """Get feature flags context for templates."""
    return {
        "features": FeatureFlags.get_enabled_flags(request, user),
        "feature_flags": FeatureFlags,
    }

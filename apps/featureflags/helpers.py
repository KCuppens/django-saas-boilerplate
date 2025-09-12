from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model

from waffle import flag_is_active, sample_is_active, switch_is_active

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser as User
else:
    User = get_user_model()


class FeatureFlags:
    """Helper class for feature flag operations"""

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
    def is_enabled(cls, flag_name: str, request=None, user: User | None = None) -> bool:
        """
        Check if a feature flag is enabled

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
        Check if a feature switch is active

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
        Check if a feature sample is active

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
    def get_enabled_flags(cls, request=None, user: User | None = None) -> dict:
        """
        Get all enabled flags

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
        cls, flag_name: str, request=None, user: User | None = None
    ) -> dict:
        """
        Get detailed status of a feature flag

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


# Convenience functions
def is_feature_enabled(flag_name: str, request=None, user: User | None = None) -> bool:
    """Convenience function to check if a feature flag is enabled"""
    return FeatureFlags.is_enabled(flag_name, request, user)


def require_feature_flag(flag_name: str):
    """Decorator to require a feature flag to be enabled"""

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


def get_feature_context(request=None, user: User | None = None) -> dict:
    """Get feature flags context for templates"""
    return {
        "features": FeatureFlags.get_enabled_flags(request, user),
        "feature_flags": FeatureFlags,
    }

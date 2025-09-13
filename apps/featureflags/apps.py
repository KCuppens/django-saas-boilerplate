"""Feature flags application configuration."""

from django.apps import AppConfig


class FeatureflagsConfig(AppConfig):
    """Configuration for the feature flags application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.featureflags"
    verbose_name = "Feature Flags"

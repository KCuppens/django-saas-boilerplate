"""Operations application configuration."""

from django.apps import AppConfig


class OpsConfig(AppConfig):
    """Configuration for the operations application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ops"
    verbose_name = "Operations"

"""Core app configuration."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Django app configuration for the core app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Core"

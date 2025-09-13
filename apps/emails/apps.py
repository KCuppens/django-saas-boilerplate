"""Email application configuration."""

from django.apps import AppConfig


class EmailsConfig(AppConfig):
    """Configuration for the emails application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.emails"
    verbose_name = "Emails"

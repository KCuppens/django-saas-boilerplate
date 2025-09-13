"""Files application configuration."""

from django.apps import AppConfig


class FilesConfig(AppConfig):
    """Configuration for the files application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.files"
    verbose_name = "Files"

"""Django app configuration for accounts."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configuration for the accounts app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Accounts"

    def ready(self):
        """Initialize the app when Django starts."""
        import apps.accounts.signals  # noqa: F401

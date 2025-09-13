"""Local development Django settings."""

# pylint: disable=wildcard-import,unused-wildcard-import
from .base import *  # noqa: F401,F403

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# Database
# Use SQLite by default for local development
# Override with DATABASE_URL env var for PostgreSQL/MySQL:
# DATABASE_URL=postgres://user:pass@localhost:5432/dbname
# DATABASE_URL=mysql://user:pass@localhost:3306/dbname
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR}/db.sqlite3")
}

# Email backend for development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# CORS settings for development
CORS_ALLOW_ALL_ORIGINS = True

# Static files (CSS, JavaScript, Images)
STATICFILES_DIRS = [BASE_DIR / "static"]

# Celery settings for development
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True

# Django Extensions (if you want to add it later)
if "django_extensions" in INSTALLED_APPS:
    INSTALLED_APPS += ["django_extensions"]

# Development logging
LOGGING["handlers"]["console"]["formatter"] = "simple"
LOGGING["root"]["level"] = "DEBUG"

# Internal IPs for django-debug-toolbar (if added later)
INTERNAL_IPS = [
    "127.0.0.1",
    "localhost",
]

# Cache (use dummy cache for development if needed)
if env.bool("USE_DUMMY_CACHE", default=False):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }

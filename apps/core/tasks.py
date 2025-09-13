"""Celery tasks for core application maintenance and health checks."""

import logging

from django.contrib.sessions.models import Session
from django.utils import timezone

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.core.tasks.cleanup_expired_sessions")
def cleanup_expired_sessions():
    """Clean up expired sessions."""
    try:
        expired_sessions = Session.objects.filter(expire_date__lt=timezone.now())
        count = expired_sessions.count()
        expired_sessions.delete()

        logger.info("Cleaned up %d expired sessions", count)
        return {"success": True, "cleaned_sessions": count}
    except Exception as e:
        logger.error("Failed to cleanup expired sessions: %s", str(e))
        return {"success": False, "error": str(e)}


@shared_task(name="apps.core.tasks.health_check")
def health_check():
    """Periodic health check task."""
    try:
        # Perform basic health checks
        from django.db import connection

        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        # Check cache connection
        from django.core.cache import cache

        cache.set("health_check", "ok", 30)
        if cache.get("health_check") != "ok":
            raise Exception("Cache not working")

        logger.info("Health check passed")
        return {"success": True, "timestamp": timezone.now().isoformat()}

    except Exception as e:
        logger.error("Health check failed: %s", str(e))
        return {"success": False, "error": str(e)}


@shared_task(name="apps.core.tasks.collect_garbage")
def collect_garbage():
    """Collect garbage and clean up temporary files."""
    try:
        import gc

        collected = gc.collect()

        logger.info("Garbage collection completed, collected %d objects", collected)
        return {"success": True, "collected_objects": collected}

    except Exception as e:
        logger.error("Garbage collection failed: %s", str(e))
        return {"success": False, "error": str(e)}

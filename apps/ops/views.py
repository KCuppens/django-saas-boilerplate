import logging

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


def health_check(request):
    """Simple health check endpoint"""
    return JsonResponse(
        {
            "status": "ok",
            "timestamp": timezone.now().isoformat(),
            "service": "django-saas-boilerplate",
        }
    )


def readiness_check(request):
    """Readiness check for container orchestration"""
    try:
        # Check database
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        # Check cache
        from django.core.cache import cache

        cache.set("readiness_check", "ok", 10)
        cache_ok = cache.get("readiness_check") == "ok"

        if cache_ok:
            return JsonResponse(
                {
                    "status": "ready",
                    "timestamp": timezone.now().isoformat(),
                    "checks": {"database": True, "cache": True},
                }
            )
        else:
            return JsonResponse(
                {
                    "status": "not_ready",
                    "timestamp": timezone.now().isoformat(),
                    "checks": {"database": True, "cache": False},
                },
                status=503,
            )

    except Exception as e:
        return JsonResponse(
            {
                "status": "not_ready",
                "timestamp": timezone.now().isoformat(),
                "error": str(e),
                "checks": {"database": False, "cache": False},
            },
            status=503,
        )


def liveness_check(request):
    """Liveness check for container orchestration"""
    return JsonResponse(
        {
            "status": "alive",
            "timestamp": timezone.now().isoformat(),
        }
    )


def version_info(request):
    """Version and build information"""
    version_data = {
        "version": "1.0.0",
        "build_time": timezone.now().isoformat(),
        "python_version": getattr(settings, "PYTHON_VERSION", "unknown"),
        "django_version": getattr(settings, "DJANGO_VERSION", "unknown"),
    }

    # Add git info if available
    try:
        import subprocess  # nosec B404

        git_hash = (
            subprocess.check_output(  # nosec B603
                ["/usr/bin/git", "rev-parse", "HEAD"], timeout=10
            )
            .decode("ascii")
            .strip()
        )
        git_branch = (
            subprocess.check_output(  # nosec B603
                ["/usr/bin/git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=10
            )
            .decode("ascii")
            .strip()
        )
        version_data.update(
            {
                "git_hash": git_hash,
                "git_branch": git_branch,
            }
        )
    except Exception as e:
        logger.warning(f"Failed to get git info: {e}")

    return JsonResponse(version_data)

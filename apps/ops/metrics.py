"""Prometheus metrics for the application"""

import logging
import time

from django.contrib.auth import get_user_model
from django.db import connection
from django.http import HttpResponse

from apps.api.models import Note
from apps.emails.models import EmailMessageLog
from apps.files.models import FileUpload

logger = logging.getLogger(__name__)

User = get_user_model()


def prometheus_metrics(request):
    """Prometheus metrics endpoint"""

    metrics = []

    # Add application metrics
    try:
        # User metrics
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()

        metrics.extend(
            [
                "# HELP django_users_total Total number of users",
                "# TYPE django_users_total counter",
                f"django_users_total {total_users}",
                "",
                "# HELP django_users_active Number of active users",
                "# TYPE django_users_active gauge",
                f"django_users_active {active_users}",
                "",
            ]
        )

        # Note metrics
        try:
            total_notes = Note.objects.count()
            public_notes = Note.objects.filter(is_public=True).count()

            metrics.extend(
                [
                    "# HELP django_notes_total Total number of notes",
                    "# TYPE django_notes_total counter",
                    f"django_notes_total {total_notes}",
                    "",
                    "# HELP django_notes_public Number of public notes",
                    "# TYPE django_notes_public gauge",
                    f"django_notes_public {public_notes}",
                    "",
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to collect notes metrics: {e}")

        # Email metrics
        try:
            total_emails = EmailMessageLog.objects.count()
            sent_emails = EmailMessageLog.objects.filter(status="sent").count()
            failed_emails = EmailMessageLog.objects.filter(status="failed").count()

            metrics.extend(
                [
                    "# HELP django_emails_total Total number of emails",
                    "# TYPE django_emails_total counter",
                    f"django_emails_total {total_emails}",
                    "",
                    "# HELP django_emails_sent Number of sent emails",
                    "# TYPE django_emails_sent counter",
                    f"django_emails_sent {sent_emails}",
                    "",
                    "# HELP django_emails_failed Number of failed emails",
                    "# TYPE django_emails_failed counter",
                    f"django_emails_failed {failed_emails}",
                    "",
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to collect notes metrics: {e}")

        # FileUpload metrics
        try:
            total_files = FileUpload.objects.count()
            public_files = FileUpload.objects.filter(is_public=True).count()
            image_files = FileUpload.objects.filter(file_type="IMAGE").count()
            document_files = FileUpload.objects.filter(file_type="DOCUMENT").count()

            metrics.extend(
                [
                    "# HELP django_files_total Total number of uploaded files",
                    "# TYPE django_files_total counter",
                    f"django_files_total {total_files}",
                    "",
                    "# HELP django_files_public Number of public files",
                    "# TYPE django_files_public gauge",
                    f"django_files_public {public_files}",
                    "",
                    "# HELP django_files_images Number of image files",
                    "# TYPE django_files_images gauge",
                    f"django_files_images {image_files}",
                    "",
                    "# HELP django_files_documents Number of document files",
                    "# TYPE django_files_documents gauge",
                    f"django_files_documents {document_files}",
                    "",
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to collect file metrics: {e}")

        # Database connection metrics
        try:
            db_start = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db_duration = time.time() - db_start

            metrics.extend(
                [
                    "# HELP django_db_connection_duration_seconds Database connection duration",
                    "# TYPE django_db_connection_duration_seconds histogram",
                    f"django_db_connection_duration_seconds {db_duration:.6f}",
                    "",
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to collect notes metrics: {e}")

        # Cache metrics (if Redis/cache available)
        try:
            from django.core.cache import cache

            cache_start = time.time()
            cache.set("metrics_test", "ok", 10)
            cache_result = cache.get("metrics_test")
            cache_duration = time.time() - cache_start

            cache_status = 1 if cache_result == "ok" else 0

            metrics.extend(
                [
                    "# HELP django_cache_status Cache availability status",
                    "# TYPE django_cache_status gauge",
                    f"django_cache_status {cache_status}",
                    "",
                    "# HELP django_cache_duration_seconds Cache operation duration",
                    "# TYPE django_cache_duration_seconds histogram",
                    f"django_cache_duration_seconds {cache_duration:.6f}",
                    "",
                ]
            )
        except Exception as e:
            logger.warning(f"Failed to collect notes metrics: {e}")

        # System uptime (approximate)
        try:
            import psutil

            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available = memory.available
            memory_total = memory.total

            # CPU usage
            cpu_percent = psutil.cpu_percent()

            metrics.extend(
                [
                    "# HELP system_uptime_seconds System uptime in seconds",
                    "# TYPE system_uptime_seconds counter",
                    f"system_uptime_seconds {uptime:.0f}",
                    "",
                    "# HELP system_memory_usage_percent Memory usage percentage",
                    "# TYPE system_memory_usage_percent gauge",
                    f"system_memory_usage_percent {memory_percent}",
                    "",
                    "# HELP system_memory_available_bytes Available memory in bytes",
                    "# TYPE system_memory_available_bytes gauge",
                    f"system_memory_available_bytes {memory_available}",
                    "",
                    "# HELP system_memory_total_bytes Total memory in bytes",
                    "# TYPE system_memory_total_bytes gauge",
                    f"system_memory_total_bytes {memory_total}",
                    "",
                    "# HELP system_cpu_usage_percent CPU usage percentage",
                    "# TYPE system_cpu_usage_percent gauge",
                    f"system_cpu_usage_percent {cpu_percent}",
                    "",
                ]
            )
        except ImportError:
            # psutil not available
            pass
        except Exception as e:
            logger.warning(f"Failed to collect notes metrics: {e}")

    except Exception as e:
        # Fallback metrics if database is unavailable
        metrics = [
            "# HELP django_app_status Application status",
            "# TYPE django_app_status gauge",
            "django_app_status 0",
            "",
            f"# Error: {str(e)}",
        ]

    # Add timestamp
    metrics.extend(
        [
            "# HELP django_metrics_timestamp Last metrics collection timestamp",
            "# TYPE django_metrics_timestamp gauge",
            f"django_metrics_timestamp {int(time.time())}",
        ]
    )

    return HttpResponse(
        "\n".join(metrics), content_type="text/plain; version=0.0.4; charset=utf-8"
    )


def health_metrics(request):
    """Simple health metrics for monitoring"""

    metrics = {"status": "healthy", "timestamp": int(time.time()), "checks": {}}

    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        metrics["checks"]["database"] = True
    except Exception:
        metrics["checks"]["database"] = False
        metrics["status"] = "unhealthy"

    # Cache check
    try:
        from django.core.cache import cache

        cache.set("health_check", "ok", 10)
        metrics["checks"]["cache"] = cache.get("health_check") == "ok"
    except Exception:
        metrics["checks"]["cache"] = False

    # Overall status
    if not all(metrics["checks"].values()):
        metrics["status"] = "degraded"

    # Convert to Prometheus format
    prometheus_metrics = [
        "# HELP django_health_status Application health status (1=healthy, 0=unhealthy)",
        "# TYPE django_health_status gauge",
        f"django_health_status {1 if metrics['status'] == 'healthy' else 0}",
        "",
        "# HELP django_health_database Database health status",
        "# TYPE django_health_database gauge",
        f"django_health_database {1 if metrics['checks']['database'] else 0}",
        "",
        "# HELP django_health_cache Cache health status",
        "# TYPE django_health_cache gauge",
        f"django_health_cache {1 if metrics['checks']['cache'] else 0}",
        "",
        "# HELP django_health_timestamp Health check timestamp",
        "# TYPE django_health_timestamp gauge",
        f"django_health_timestamp {metrics['timestamp']}",
    ]

    return HttpResponse(
        "\n".join(prometheus_metrics),
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )

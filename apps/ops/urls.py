from django.urls import path

from .metrics import health_metrics, prometheus_metrics
from .views import health_check, liveness_check, readiness_check, version_info

urlpatterns = [
    # Health check endpoints
    path("healthz/", health_check, name="health_check"),
    path("readyz/", readiness_check, name="readiness_check"),
    path("livez/", liveness_check, name="liveness_check"),
    path("version/", version_info, name="version_info"),
    # Metrics endpoints
    path("metrics/", prometheus_metrics, name="prometheus_metrics"),
    path("metrics/health/", health_metrics, name="health_metrics"),
]

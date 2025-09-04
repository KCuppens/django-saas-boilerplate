from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import HealthCheckViewSet, NoteViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(r"notes", NoteViewSet, basename="note")
router.register(r"health", HealthCheckViewSet, basename="health")

urlpatterns = [
    # API v1 endpoints
    path("", include(router.urls)),
    # Include other app APIs
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.files.urls")),  # Files API
]

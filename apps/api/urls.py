"""URL configuration for API app."""

from django.urls import include, path

from rest_framework.routers import DefaultRouter

from .views import APIKeyViewSet, HealthCheckViewSet, NoteViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(r"notes", NoteViewSet, basename="note")
router.register(r"health", HealthCheckViewSet, basename="healthcheck")
router.register(r"api-keys", APIKeyViewSet, basename="apikey")

urlpatterns = [
    # API v1 endpoints
    path("", include(router.urls)),
    # Include other app APIs
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.files.urls")),  # Files API
]

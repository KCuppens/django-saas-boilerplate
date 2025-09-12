from django.db.models import Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
)
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsOwnerOrAdmin

from .models import APIKey, Note
from .serializers import (
    APIKeyCreateSerializer,
    APIKeySerializer,
    HealthCheckSerializer,
    NoteCreateUpdateSerializer,
    NoteSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="List notes",
        description=(
            "Get a list of notes. Users can see their own notes and public notes."
        ),
        parameters=[
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                description="Search in title and content",
            ),
            OpenApiParameter(
                name="tags",
                type=OpenApiTypes.STR,
                description="Filter by tags (comma-separated)",
            ),
            OpenApiParameter(
                name="is_public",
                type=OpenApiTypes.BOOL,
                description="Filter by public status",
            ),
        ],
    ),
    create=extend_schema(
        summary="Create note",
        description=(
            "Create a new note. The authenticated user will be set as the creator."
        ),
    ),
    retrieve=extend_schema(
        summary="Get note",
        description=(
            "Get a specific note. Users can only access their own notes or "
            "public notes."
        ),
    ),
    update=extend_schema(
        summary="Update note",
        description="Update a note. Users can only update their own notes.",
    ),
    partial_update=extend_schema(
        summary="Partially update note",
        description=("Partially update a note. Users can only update their own notes."),
    ),
    destroy=extend_schema(
        summary="Delete note",
        description="Delete a note. Users can only delete their own notes.",
    ),
)
class NoteViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notes"""

    serializer_class = NoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_queryset(self):
        """Get notes based on user permissions"""
        queryset = Note.objects.select_related("created_by", "updated_by")

        # Users can see their own notes and public notes
        if not self.request.user.is_admin():
            queryset = queryset.filter(
                Q(created_by=self.request.user) | Q(is_public=True)
            )

        # Apply filters
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(content__icontains=search)
            )

        tags = self.request.query_params.get("tags")
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",")]
            for tag in tag_list:
                queryset = queryset.filter(tags__icontains=tag)

        is_public = self.request.query_params.get("is_public")
        if is_public is not None:
            queryset = queryset.filter(is_public=is_public.lower() == "true")

        return queryset

    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action in ["create", "update", "partial_update"]:
            return NoteCreateUpdateSerializer
        return NoteSerializer

    def perform_create(self, serializer):
        """Set the creator when creating a note"""
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        """Set the updater when updating a note"""
        serializer.save(updated_by=self.request.user)

    @extend_schema(
        summary="Get my notes",
        description="Get all notes created by the current user.",
    )
    @action(detail=False, methods=["get"])
    def my_notes(self, request):
        """Get notes created by the current user"""
        queryset = self.get_queryset().filter(created_by=request.user)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Get public notes",
        description="Get all public notes.",
    )
    @action(detail=False, methods=["get"])
    def public(self, request):
        """Get public notes"""
        queryset = self.get_queryset().filter(is_public=True)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Toggle note visibility",
        description="Toggle the public/private status of a note.",
    )
    @action(detail=True, methods=["post"])
    def toggle_visibility(self, request, pk=None):
        """Toggle note visibility between public and private"""
        note = self.get_object()
        note.is_public = not note.is_public
        note.updated_by = request.user
        note.save(update_fields=["is_public", "updated_by", "updated_at"])

        serializer = self.get_serializer(note)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="Health check",
        description="Get application health status and system information.",
    ),
)
class HealthCheckViewSet(viewsets.ViewSet):
    """ViewSet for health checks and system status"""

    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: HealthCheckSerializer})
    def list(self, request):
        """Comprehensive health check"""
        health_data = {
            "status": "healthy",
            "timestamp": timezone.now(),
            "database": self._check_database(),
            "cache": self._check_cache(),
            "services": {},
            "errors": [],
        }

        # Check Celery (if available)
        celery_status = self._check_celery()
        if celery_status is not None:
            health_data["celery"] = celery_status

        # Add version info
        health_data["version"] = self._get_version()

        # Add system metrics (optional)
        if request.user.is_authenticated and request.user.is_staff:
            health_data.update(self._get_system_metrics())

        # Determine overall status
        checks = [health_data["database"], health_data["cache"]]
        if "celery" in health_data:
            checks.append(health_data["celery"])

        if not all(checks):
            health_data["status"] = "unhealthy"
            return Response(health_data, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        serializer = HealthCheckSerializer(health_data)
        return Response(serializer.data)

    def _check_database(self):
        """Check database connectivity"""
        try:
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            return False

    def _check_cache(self):
        """Check cache connectivity"""
        try:
            from django.core.cache import cache

            test_key = "health_check_test"
            cache.set(test_key, "ok", 10)
            return cache.get(test_key) == "ok"
        except Exception:
            return False

    def _check_celery(self):
        """Check Celery worker availability"""
        try:
            from celery import current_app

            inspect = current_app.control.inspect()
            stats = inspect.stats()
            return stats is not None and len(stats) > 0
        except Exception:
            return None  # Celery not available or configured

    def _get_version(self):
        """Get application version"""
        try:
            # You can implement version detection here
            # For example, read from a VERSION file or git tag
            return "1.0.0"
        except Exception:
            return "unknown"

    def _get_system_metrics(self):
        """Get system metrics (for staff users only)"""
        try:
            import time

            import psutil

            # Get uptime (approximate)
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            uptime_hours = uptime_seconds / 3600

            return {
                "uptime": f"{uptime_hours:.1f} hours",
                "memory_usage": psutil.virtual_memory().percent,
                "cpu_usage": psutil.cpu_percent(),
            }
        except ImportError:
            # psutil not available
            return {}
        except Exception:
            return {}

    @extend_schema(
        summary="Ready check",
        description="Check if the application is ready to serve requests.",
    )
    @action(detail=False, methods=["get"])
    def ready(self, request):
        """Readiness check (for Kubernetes probes)"""
        # Check essential services
        if not self._check_database():
            return Response(
                {"status": "not ready", "reason": "database unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not self._check_cache():
            return Response(
                {"status": "not ready", "reason": "cache unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({"status": "ready"})

    @extend_schema(
        summary="Live check", description="Check if the application is alive."
    )
    @action(detail=False, methods=["get"])
    def live(self, request):
        """Liveness check (for Kubernetes probes)"""
        return Response({"status": "alive", "timestamp": timezone.now()})


@extend_schema_view(
    list=extend_schema(
        summary="List API keys",
        description="Get a list of API keys for the authenticated user.",
    ),
    create=extend_schema(
        summary="Create API key",
        description="Create a new API key for the authenticated user.",
    ),
    retrieve=extend_schema(
        summary="Get API key",
        description="Get a specific API key.",
    ),
    update=extend_schema(
        summary="Update API key",
        description="Update an API key.",
    ),
    partial_update=extend_schema(
        summary="Partially update API key",
        description="Partially update an API key.",
    ),
    destroy=extend_schema(
        summary="Delete API key",
        description="Delete an API key.",
    ),
)
class APIKeyViewSet(viewsets.ModelViewSet):
    """ViewSet for managing API keys"""

    serializer_class = APIKeySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Get API keys for the current user"""
        return APIKey.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        """Return appropriate serializer class"""
        if self.action == "create":
            return APIKeyCreateSerializer
        return APIKeySerializer

    def perform_create(self, serializer):
        """Set the user when creating an API key"""
        serializer.save(user=self.request.user)

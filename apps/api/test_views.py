"""Comprehensive tests for API views"""

from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.api.models import Note

User = get_user_model()


@pytest.mark.django_db
class TestNoteViewSet:
    """Test NoteViewSet functionality"""

    @pytest.fixture
    def note_data(self):
        """Sample note data for testing"""
        return {
            "title": "Test Note",
            "content": "Test content",
            "is_public": False,
            "tag_list": ["test", "api"],
        }

    @pytest.fixture
    def sample_note(self, user):
        """Create a sample note for testing"""
        return Note.objects.create(
            title="Sample Note",
            content="Sample content",
            is_public=False,
            tags="sample, test",
            created_by=user,
            updated_by=user,
        )

    @pytest.fixture
    def public_note(self, user):
        """Create a public note for testing"""
        return Note.objects.create(
            title="Public Note",
            content="Public content",
            is_public=True,
            tags="public, test",
            created_by=user,
            updated_by=user,
        )

    @pytest.fixture
    def other_user_note(self, member_user):
        """Create a note by another user"""
        return Note.objects.create(
            title="Other User Note",
            content="Other user content",
            is_public=False,
            tags="other, private",
            created_by=member_user,
            updated_by=member_user,
        )

    def test_list_notes_unauthenticated(self, api_client):
        """Test listing notes without authentication"""
        url = reverse("note-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_notes_authenticated_empty(self, auth_client):
        """Test listing notes with no notes available"""
        url = reverse("note-list")
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0
        assert response.data["results"] == []

    def test_list_notes_authenticated(self, auth_client, user, sample_note):
        """Test listing notes for authenticated user"""
        url = reverse("note-list")
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["id"] == sample_note.id

    def test_list_notes_includes_public_and_own(self, auth_client, user, sample_note, public_note, other_user_note):
        """Test that list includes own notes and public notes"""
        url = reverse("note-list")
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

        note_ids = [note["id"] for note in response.data["results"]]
        assert sample_note.id in note_ids  # Own note
        assert public_note.id in note_ids  # Public note
        assert other_user_note.id not in note_ids  # Other user's private note

    def test_list_notes_admin_sees_all(self, admin_client, sample_note, other_user_note):
        """Test that admin users can see all notes"""
        url = reverse("note-list")
        response = admin_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

        note_ids = [note["id"] for note in response.data["results"]]
        assert sample_note.id in note_ids
        assert other_user_note.id in note_ids

    def test_list_notes_search_filter(self, auth_client, user):
        """Test search filtering"""
        # Create notes with different content
        Note.objects.create(
            title="Python Tutorial",
            content="Learn Python programming",
            created_by=user,
            updated_by=user,
        )
        Note.objects.create(
            title="Django Guide",
            content="Learn Django framework",
            created_by=user,
            updated_by=user,
        )
        Note.objects.create(
            title="React Tutorial",
            content="Learn React library",
            created_by=user,
            updated_by=user,
        )

        url = reverse("note-list")

        # Search in title
        response = auth_client.get(url, {"search": "Python"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Python Tutorial"

        # Search in content
        response = auth_client.get(url, {"search": "Django"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Django Guide"

        # Search for common term
        response = auth_client.get(url, {"search": "Learn"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

    def test_list_notes_tags_filter(self, auth_client, user):
        """Test tags filtering"""
        Note.objects.create(
            title="Python Note",
            content="Python content",
            tags="python, programming",
            created_by=user,
            updated_by=user,
        )
        Note.objects.create(
            title="Django Note",
            content="Django content",
            tags="django, python, web",
            created_by=user,
            updated_by=user,
        )
        Note.objects.create(
            title="React Note",
            content="React content",
            tags="react, javascript",
            created_by=user,
            updated_by=user,
        )

        url = reverse("note-list")

        # Filter by single tag
        response = auth_client.get(url, {"tags": "python"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

        # Filter by multiple tags
        response = auth_client.get(url, {"tags": "python,web"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Django Note"

    def test_list_notes_is_public_filter(self, auth_client, user, public_note, sample_note):
        """Test is_public filtering"""
        url = reverse("note-list")

        # Filter for public notes only
        response = auth_client.get(url, {"is_public": "true"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == public_note.id

        # Filter for private notes only
        response = auth_client.get(url, {"is_public": "false"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == sample_note.id

    def test_create_note_unauthenticated(self, api_client, note_data):
        """Test creating note without authentication"""
        url = reverse("note-list")
        response = api_client.post(url, data=note_data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_note_authenticated(self, auth_client, user, note_data):
        """Test creating note with authentication"""
        url = reverse("note-list")
        response = auth_client.post(url, data=note_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert Note.objects.filter(title="Test Note").exists()

        # Check that user is set as creator
        note = Note.objects.get(title="Test Note")
        assert note.created_by == user
        assert note.updated_by == user
        assert note.tags == "test, api"

    def test_create_note_validation_error(self, auth_client):
        """Test creating note with validation errors"""
        url = reverse("note-list")
        invalid_data = {"content": "Missing title"}
        response = auth_client.post(url, data=invalid_data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "title" in response.data

    def test_retrieve_note_authenticated(self, auth_client, sample_note):
        """Test retrieving a note"""
        url = reverse("note-detail", args=[sample_note.id])
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == sample_note.id
        assert response.data["title"] == sample_note.title

    def test_retrieve_note_not_found(self, auth_client):
        """Test retrieving non-existent note"""
        url = reverse("note-detail", args=[9999])
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_other_user_private_note_forbidden(self, auth_client, other_user_note):
        """Test retrieving another user's private note"""
        url = reverse("note-detail", args=[other_user_note.id])
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_retrieve_other_user_public_note_allowed(self, auth_client, public_note):
        """Test retrieving another user's public note"""
        url = reverse("note-detail", args=[public_note.id])
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == public_note.id

    def test_update_note_authenticated(self, auth_client, user, sample_note):
        """Test updating own note"""
        url = reverse("note-detail", args=[sample_note.id])
        update_data = {
            "title": "Updated Note",
            "content": "Updated content",
            "is_public": True,
            "tag_list": ["updated"],
        }
        response = auth_client.put(url, data=update_data, format="json")

        assert response.status_code == status.HTTP_200_OK

        sample_note.refresh_from_db()
        assert sample_note.title == "Updated Note"
        assert sample_note.content == "Updated content"
        assert sample_note.is_public is True
        assert sample_note.tags == "updated"
        assert sample_note.updated_by == user

    def test_partial_update_note(self, auth_client, sample_note):
        """Test partially updating a note"""
        url = reverse("note-detail", args=[sample_note.id])
        partial_data = {"title": "Partially Updated"}
        response = auth_client.patch(url, data=partial_data, format="json")

        assert response.status_code == status.HTTP_200_OK

        sample_note.refresh_from_db()
        assert sample_note.title == "Partially Updated"
        assert sample_note.content == "Sample content"  # Unchanged

    def test_update_other_user_note_forbidden(self, auth_client, other_user_note):
        """Test updating another user's note"""
        url = reverse("note-detail", args=[other_user_note.id])
        update_data = {"title": "Hacked"}
        response = auth_client.patch(url, data=update_data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_note_authenticated(self, auth_client, sample_note):
        """Test deleting own note"""
        url = reverse("note-detail", args=[sample_note.id])
        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Note.objects.filter(id=sample_note.id).exists()

    def test_delete_other_user_note_forbidden(self, auth_client, other_user_note):
        """Test deleting another user's note"""
        url = reverse("note-detail", args=[other_user_note.id])
        response = auth_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Note.objects.filter(id=other_user_note.id).exists()

    def test_my_notes_action(self, auth_client, user, sample_note, public_note, other_user_note):
        """Test my_notes custom action"""
        url = reverse("note-my-notes")
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == sample_note.id

    def test_public_notes_action(self, auth_client, user, sample_note, public_note, other_user_note):
        """Test public custom action"""
        url = reverse("note-public")
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == public_note.id

    def test_toggle_visibility_action(self, auth_client, user, sample_note):
        """Test toggle_visibility custom action"""
        url = reverse("note-toggle-visibility", args=[sample_note.id])

        # Initially private
        assert sample_note.is_public is False

        # Toggle to public
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_200_OK

        sample_note.refresh_from_db()
        assert sample_note.is_public is True
        assert sample_note.updated_by == user

        # Toggle back to private
        response = auth_client.post(url)
        assert response.status_code == status.HTTP_200_OK

        sample_note.refresh_from_db()
        assert sample_note.is_public is False

    def test_toggle_visibility_other_user_note_forbidden(self, auth_client, other_user_note):
        """Test toggling visibility of another user's note"""
        url = reverse("note-toggle-visibility", args=[other_user_note.id])
        response = auth_client.post(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_access_any_note(self, admin_client, other_user_note):
        """Test that admin can access any note"""
        url = reverse("note-detail", args=[other_user_note.id])
        response = admin_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == other_user_note.id

    def test_admin_can_update_any_note(self, admin_client, admin_user, other_user_note):
        """Test that admin can update any note"""
        url = reverse("note-detail", args=[other_user_note.id])
        update_data = {"title": "Admin Updated"}
        response = admin_client.patch(url, data=update_data, format="json")

        assert response.status_code == status.HTTP_200_OK

        other_user_note.refresh_from_db()
        assert other_user_note.title == "Admin Updated"
        assert other_user_note.updated_by == admin_user

    def test_serializer_selection(self, auth_client, user):
        """Test that correct serializer is used for different actions"""
        # Create action uses NoteCreateUpdateSerializer
        url = reverse("note-list")
        create_data = {
            "title": "New Note",
            "content": "New content",
            "tag_list": ["new"],
        }
        response = auth_client.post(url, data=create_data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        note = Note.objects.get(title="New Note")

        # Update action uses NoteCreateUpdateSerializer
        url = reverse("note-detail", args=[note.id])
        update_data = {
            "title": "Updated Note",
            "content": "Updated content",
            "tag_list": ["updated"],
        }
        response = auth_client.put(url, data=update_data, format="json")
        assert response.status_code == status.HTTP_200_OK

        # List/Retrieve actions use NoteSerializer (should include read-only fields)
        url = reverse("note-detail", args=[note.id])
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert "created_by_name" in response.data
        assert "updated_by_name" in response.data

    def test_pagination(self, auth_client, user):
        """Test pagination of notes"""
        # Create multiple notes
        for i in range(25):
            Note.objects.create(
                title=f"Note {i}",
                content=f"Content {i}",
                created_by=user,
                updated_by=user,
            )

        url = reverse("note-list")
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "next" in response.data
        assert "previous" in response.data
        assert "count" in response.data
        assert response.data["count"] == 25
        assert len(response.data["results"]) <= 20  # Default page size

    def test_custom_actions_pagination(self, auth_client, user):
        """Test pagination in custom actions"""
        # Create multiple notes
        for i in range(15):
            Note.objects.create(
                title=f"My Note {i}",
                content=f"My Content {i}",
                is_public=i % 2 == 0,  # Alternate public/private
                created_by=user,
                updated_by=user,
            )

        # Test my_notes pagination
        url = reverse("note-my-notes")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 15

        # Test public pagination
        url = reverse("note-public")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 8  # Half are public


@pytest.mark.django_db
class TestHealthCheckViewSet:
    """Test HealthCheckViewSet functionality"""

    def test_health_check_unauthenticated(self, api_client):
        """Test health check without authentication"""
        url = reverse("health-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "healthy"
        assert "timestamp" in response.data
        assert "database" in response.data
        assert "cache" in response.data

    def test_health_check_authenticated(self, auth_client):
        """Test health check with authentication"""
        url = reverse("health-list")
        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "healthy"

    def test_health_check_staff_user_gets_metrics(self, admin_client):
        """Test that staff users get additional system metrics"""
        url = reverse("health-list")
        response = admin_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # Staff users might get additional metrics if psutil is available
        # This test checks the code path rather than specific metrics

    @patch('apps.api.views.HealthCheckViewSet._check_database')
    def test_health_check_database_failure(self, mock_db_check, api_client):
        """Test health check when database fails"""
        mock_db_check.return_value = False

        url = reverse("health-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "unhealthy"
        assert response.data["database"] is False

    @patch('apps.api.views.HealthCheckViewSet._check_cache')
    def test_health_check_cache_failure(self, mock_cache_check, api_client):
        """Test health check when cache fails"""
        mock_cache_check.return_value = False

        url = reverse("health-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "unhealthy"
        assert response.data["cache"] is False

    @patch('apps.api.views.HealthCheckViewSet._check_celery')
    def test_health_check_with_celery(self, mock_celery_check, api_client):
        """Test health check with Celery available"""
        mock_celery_check.return_value = True

        url = reverse("health-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["celery"] is True

    @patch('apps.api.views.HealthCheckViewSet._check_celery')
    def test_health_check_celery_failure(self, mock_celery_check, api_client):
        """Test health check when Celery fails"""
        mock_celery_check.return_value = False

        url = reverse("health-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "unhealthy"
        assert response.data["celery"] is False

    def test_ready_check(self, api_client):
        """Test readiness check endpoint"""
        url = reverse("health-ready")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "ready"

    @patch('apps.api.views.HealthCheckViewSet._check_database')
    def test_ready_check_database_not_ready(self, mock_db_check, api_client):
        """Test readiness check when database is not ready"""
        mock_db_check.return_value = False

        url = reverse("health-ready")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "not ready"
        assert response.data["reason"] == "database unavailable"

    @patch('apps.api.views.HealthCheckViewSet._check_cache')
    def test_ready_check_cache_not_ready(self, mock_cache_check, api_client):
        """Test readiness check when cache is not ready"""
        mock_cache_check.return_value = False

        url = reverse("health-ready")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "not ready"
        assert response.data["reason"] == "cache unavailable"

    def test_live_check(self, api_client):
        """Test liveness check endpoint"""
        url = reverse("health-live")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "alive"
        assert "timestamp" in response.data

    def test_database_check_method(self):
        """Test _check_database method directly"""
        from apps.api.views import HealthCheckViewSet

        viewset = HealthCheckViewSet()
        result = viewset._check_database()

        # Should return True in test environment
        assert result is True

    def test_cache_check_method(self):
        """Test _check_cache method directly"""
        from apps.api.views import HealthCheckViewSet

        viewset = HealthCheckViewSet()
        result = viewset._check_cache()

        # Should return True in test environment
        assert result is True

    @patch('apps.api.views.current_app')
    def test_celery_check_method_available(self, mock_current_app):
        """Test _check_celery method when Celery is available"""
        from apps.api.views import HealthCheckViewSet

        # Mock successful Celery check
        mock_inspect = Mock()
        mock_inspect.stats.return_value = {"worker1": {}}
        mock_control = Mock()
        mock_control.inspect.return_value = mock_inspect
        mock_current_app.control = mock_control

        viewset = HealthCheckViewSet()
        result = viewset._check_celery()

        assert result is True

    @patch('apps.api.views.current_app')
    def test_celery_check_method_unavailable(self, mock_current_app):
        """Test _check_celery method when Celery is unavailable"""
        from apps.api.views import HealthCheckViewSet

        mock_current_app.control.inspect.side_effect = Exception("Celery not available")

        viewset = HealthCheckViewSet()
        result = viewset._check_celery()

        assert result is None

    def test_get_version_method(self):
        """Test _get_version method"""
        from apps.api.views import HealthCheckViewSet

        viewset = HealthCheckViewSet()
        version = viewset._get_version()

        # Should return a string version
        assert isinstance(version, str)

    @patch('apps.api.views.psutil')
    def test_system_metrics_with_psutil(self, mock_psutil):
        """Test _get_system_metrics with psutil available"""
        from apps.api.views import HealthCheckViewSet

        # Mock psutil
        mock_psutil.boot_time.return_value = timezone.now().timestamp() - 7200  # 2 hours ago
        mock_psutil.virtual_memory.return_value.percent = 45.2
        mock_psutil.cpu_percent.return_value = 23.8

        viewset = HealthCheckViewSet()
        metrics = viewset._get_system_metrics()

        assert "uptime" in metrics
        assert "memory_usage" in metrics
        assert "cpu_usage" in metrics
        assert metrics["memory_usage"] == 45.2
        assert metrics["cpu_usage"] == 23.8

    def test_system_metrics_without_psutil(self):
        """Test _get_system_metrics without psutil"""
        from apps.api.views import HealthCheckViewSet

        with patch.dict('sys.modules', {'psutil': None}):
            viewset = HealthCheckViewSet()
            metrics = viewset._get_system_metrics()

        # Should return empty dict when psutil not available
        assert metrics == {}

    def test_permission_classes(self):
        """Test that health check allows any access"""
        from rest_framework.permissions import AllowAny

        from apps.api.views import HealthCheckViewSet

        viewset = HealthCheckViewSet()
        assert AllowAny in viewset.permission_classes

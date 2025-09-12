"""Integration tests for complete API workflows"""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestNoteWorkflows:
    """Integration tests for complete Note workflows"""

    @pytest.fixture
    def user(self):
        """Create test user"""
        return User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User",
        )

    @pytest.fixture
    def other_user(self):
        """Create another test user"""
        return User.objects.create_user(
            email="other@example.com",
            password="otherpass123",
            name="Other User",
        )

    @pytest.fixture
    def admin_user(self):
        """Create admin user"""
        return User.objects.create_user(
            email="admin@example.com",
            password="adminpass123",
            name="Admin User",
            is_staff=True,
            is_superuser=True,
        )

    @pytest.fixture
    def auth_client(self, user):
        """Create authenticated API client"""
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    @pytest.fixture
    def other_auth_client(self, other_user):
        """Create authenticated API client for other user"""
        client = APIClient()
        client.force_authenticate(user=other_user)
        return client

    @pytest.fixture
    def admin_client(self, admin_user):
        """Create admin API client"""
        client = APIClient()
        client.force_authenticate(user=admin_user)
        return client

    def test_complete_note_crud_workflow(self, auth_client, user):
        """Test complete CRUD workflow for notes"""
        # 1. Create a note
        create_data = {
            "title": "My First Note",
            "content": "This is my first note content",
            "is_public": False,
            "tag_list": ["personal", "first"]
        }

        create_url = reverse("note-list")
        response = auth_client.post(create_url, data=create_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "My First Note"
        assert response.data["content"] == "This is my first note content"
        assert response.data["is_public"] is False
        assert response.data["tag_list"] == ["personal", "first"]

        note_id = response.data["id"]

        # 2. Read the note
        detail_url = reverse("note-detail", args=[note_id])
        response = auth_client.get(detail_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == note_id
        assert response.data["created_by_name"] == user.get_full_name()

        # 3. Update the note
        update_data = {
            "title": "My Updated Note",
            "content": "This is updated content",
            "is_public": True,
            "tag_list": ["updated", "public"]
        }

        response = auth_client.put(detail_url, data=update_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "My Updated Note"
        assert response.data["content"] == "This is updated content"
        assert response.data["is_public"] is True
        assert response.data["tag_list"] == ["updated", "public"]

        # 4. Partial update the note
        partial_data = {"title": "Partially Updated Note"}

        response = auth_client.patch(detail_url, data=partial_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Partially Updated Note"
        assert response.data["content"] == "This is updated content"  # Unchanged

        # 5. List notes and verify it's there
        list_url = reverse("note-list")
        response = auth_client.get(list_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == note_id

        # 6. Delete the note
        response = auth_client.delete(detail_url)

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # 7. Verify note is deleted
        response = auth_client.get(detail_url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

        response = auth_client.get(list_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    def test_note_sharing_workflow(self, auth_client, other_auth_client, user, other_user):
        """Test note sharing between users"""
        # 1. User creates a private note
        create_data = {
            "title": "Private Note",
            "content": "This is private",
            "is_public": False,
            "tag_list": ["private"]
        }

        create_url = reverse("note-list")
        response = auth_client.post(create_url, data=create_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        note_id = response.data["id"]

        # 2. Other user cannot see private note
        detail_url = reverse("note-detail", args=[note_id])
        response = other_auth_client.get(detail_url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        # 3. Other user cannot see private note in list
        list_url = reverse("note-list")
        response = other_auth_client.get(list_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

        # 4. User makes note public using toggle action
        toggle_url = reverse("note-toggle-visibility", args=[note_id])
        response = auth_client.post(toggle_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_public"] is True

        # 5. Now other user can see the note
        response = other_auth_client.get(detail_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Private Note"

        # 6. Other user can see public note in list
        response = other_auth_client.get(list_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

        # 7. Other user can see it in public notes endpoint
        public_url = reverse("note-public")
        response = other_auth_client.get(public_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

        # 8. But other user still cannot modify it
        update_data = {"title": "Hacked Title"}
        response = other_auth_client.patch(detail_url, data=update_data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_note_filtering_workflow(self, auth_client, user):
        """Test complete filtering workflow"""
        # 1. Create multiple notes with different attributes
        notes_data = [
            {
                "title": "Python Tutorial",
                "content": "Learn Python programming",
                "is_public": True,
                "tag_list": ["python", "tutorial", "programming"]
            },
            {
                "title": "Django Guide",
                "content": "Learn Django web framework",
                "is_public": False,
                "tag_list": ["django", "python", "web"]
            },
            {
                "title": "React Tutorial",
                "content": "Learn React for frontend",
                "is_public": True,
                "tag_list": ["react", "javascript", "frontend"]
            },
            {
                "title": "Database Design",
                "content": "SQL database design principles",
                "is_public": False,
                "tag_list": ["database", "sql", "design"]
            }
        ]

        create_url = reverse("note-list")
        created_notes = []

        for note_data in notes_data:
            response = auth_client.post(create_url, data=note_data, format="json")
            assert response.status_code == status.HTTP_201_CREATED
            created_notes.append(response.data)

        list_url = reverse("note-list")

        # 2. Test search filtering
        response = auth_client.get(list_url, {"search": "Python"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Python Tutorial"

        response = auth_client.get(list_url, {"search": "Learn"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3  # Python, Django, React

        # 3. Test tag filtering
        response = auth_client.get(list_url, {"tags": "python"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2  # Python and Django

        response = auth_client.get(list_url, {"tags": "python,web"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1  # Only Django has both tags

        # 4. Test is_public filtering
        response = auth_client.get(list_url, {"is_public": "true"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2  # Python and React

        response = auth_client.get(list_url, {"is_public": "false"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2  # Django and Database

        # 5. Test combined filtering
        response = auth_client.get(list_url, {
            "search": "Tutorial",
            "is_public": "true"
        })
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2  # Python and React tutorials that are public

        # 6. Test my_notes endpoint
        my_notes_url = reverse("note-my-notes")
        response = auth_client.get(my_notes_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 4  # All notes belong to user

        # 7. Test public endpoint
        public_url = reverse("note-public")
        response = auth_client.get(public_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2  # Python and React are public

    def test_admin_access_workflow(self, auth_client, admin_client, user, admin_user):
        """Test admin access workflow"""
        # 1. Regular user creates a private note
        create_data = {
            "title": "User Private Note",
            "content": "User's private content",
            "is_public": False,
            "tag_list": ["private", "user"]
        }

        create_url = reverse("note-list")
        response = auth_client.post(create_url, data=create_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        note_id = response.data["id"]

        # 2. Admin can see the private note in list
        list_url = reverse("note-list")
        response = admin_client.get(list_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

        # 3. Admin can access the private note directly
        detail_url = reverse("note-detail", args=[note_id])
        response = admin_client.get(detail_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "User Private Note"

        # 4. Admin can modify the note
        update_data = {"title": "Admin Modified Note"}
        response = admin_client.patch(detail_url, data=update_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Admin Modified Note"
        assert response.data["updated_by"] == admin_user.id

        # 5. Admin can toggle visibility
        toggle_url = reverse("note-toggle-visibility", args=[note_id])
        response = admin_client.post(toggle_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_public"] is True

        # 6. Admin can delete any note
        response = admin_client.delete(detail_url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_pagination_workflow(self, auth_client, user):
        """Test pagination workflow"""
        # 1. Create many notes
        create_url = reverse("note-list")
        note_ids = []

        for i in range(25):
            create_data = {
                "title": f"Note {i:02d}",
                "content": f"Content for note {i}",
                "is_public": i % 2 == 0,  # Alternate public/private
                "tag_list": [f"tag{i}", "batch"]
            }

            response = auth_client.post(create_url, data=create_data, format="json")
            assert response.status_code == status.HTTP_201_CREATED
            note_ids.append(response.data["id"])

        # 2. Test first page
        list_url = reverse("note-list")
        response = auth_client.get(list_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 25
        assert len(response.data["results"]) <= 20  # Page size
        assert response.data["next"] is not None
        assert response.data["previous"] is None

        # 3. Navigate to next page
        next_url = response.data["next"]
        response = auth_client.get(next_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["previous"] is not None
        assert len(response.data["results"]) == 5  # Remaining notes

        # 4. Test pagination with filtering
        response = auth_client.get(list_url, {"is_public": "true"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 13  # Half + 1 are public

        # 5. Test pagination in custom actions
        my_notes_url = reverse("note-my-notes")
        response = auth_client.get(my_notes_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 25
        assert response.data["next"] is not None

    def test_error_handling_workflow(self, auth_client, user):
        """Test error handling throughout the workflow"""
        # 1. Test validation errors on create
        create_url = reverse("note-list")
        invalid_data = {"content": "Missing title"}

        response = auth_client.post(create_url, data=invalid_data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "title" in response.data

        # 2. Test accessing non-existent note
        detail_url = reverse("note-detail", args=[99999])
        response = auth_client.get(detail_url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # 3. Test updating non-existent note
        update_data = {"title": "Updated"}
        response = auth_client.patch(detail_url, data=update_data, format="json")
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # 4. Test deleting non-existent note
        response = auth_client.delete(detail_url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # 5. Create a valid note for permission tests
        create_data = {
            "title": "Permission Test Note",
            "content": "Test content",
            "is_public": False
        }
        response = auth_client.post(create_url, data=create_data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        note_id = response.data["id"]

        # 6. Test unauthenticated access
        client = APIClient()  # No auth
        detail_url = reverse("note-detail", args=[note_id])

        response = client.get(detail_url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response = client.patch(detail_url, data=update_data, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response = client.delete(detail_url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestHealthCheckWorkflows:
    """Integration tests for health check workflows"""

    def test_complete_health_check_workflow(self):
        """Test complete health check workflow"""
        client = APIClient()  # No auth needed

        # 1. Basic health check
        health_url = reverse("health-list")
        response = client.get(health_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "healthy"
        assert "timestamp" in response.data
        assert "database" in response.data
        assert "cache" in response.data
        assert response.data["database"] is True
        assert response.data["cache"] is True

        # 2. Ready check
        ready_url = reverse("health-ready")
        response = client.get(ready_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "ready"

        # 3. Live check
        live_url = reverse("health-live")
        response = client.get(live_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "alive"
        assert "timestamp" in response.data

    @patch('apps.api.views.HealthCheckViewSet._check_database')
    def test_unhealthy_service_workflow(self, mock_db_check):
        """Test workflow when service is unhealthy"""
        mock_db_check.return_value = False

        client = APIClient()

        # 1. Health check shows unhealthy
        health_url = reverse("health-list")
        response = client.get(health_url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "unhealthy"
        assert response.data["database"] is False

        # 2. Ready check fails
        ready_url = reverse("health-ready")
        response = client.get(ready_url)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["status"] == "not ready"
        assert response.data["reason"] == "database unavailable"

        # 3. Live check still works (different purpose)
        live_url = reverse("health-live")
        response = client.get(live_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "alive"

    def test_staff_health_check_workflow(self, admin_user):
        """Test health check with staff user gets additional metrics"""
        client = APIClient()
        client.force_authenticate(user=admin_user)

        health_url = reverse("health-list")
        response = client.get(health_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "healthy"

        # Staff users might get additional system metrics
        # The exact metrics depend on whether psutil is available
        # This test ensures the staff code path is exercised


@pytest.mark.django_db
class TestConcurrentOperations:
    """Test concurrent operations and race conditions"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(
            email="concurrent@example.com",
            password="testpass123",
            name="Concurrent User",
        )

    @pytest.fixture
    def auth_client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_concurrent_note_updates(self, auth_client, user):
        """Test concurrent updates to the same note"""
        # Create a note
        create_data = {
            "title": "Concurrent Test",
            "content": "Original content",
            "is_public": False
        }

        create_url = reverse("note-list")
        response = auth_client.post(create_url, data=create_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        note_id = response.data["id"]
        detail_url = reverse("note-detail", args=[note_id])

        # Simulate concurrent updates
        update_data_1 = {"title": "Update 1"}
        update_data_2 = {"title": "Update 2"}

        response_1 = auth_client.patch(detail_url, data=update_data_1, format="json")
        response_2 = auth_client.patch(detail_url, data=update_data_2, format="json")

        # Both should succeed (last write wins in this simple case)
        assert response_1.status_code == status.HTTP_200_OK
        assert response_2.status_code == status.HTTP_200_OK

        # Check final state
        response = auth_client.get(detail_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Update 2"  # Last update wins

    def test_concurrent_visibility_toggles(self, auth_client, user):
        """Test concurrent visibility toggles"""
        # Create a note
        create_data = {
            "title": "Toggle Test",
            "content": "Toggle content",
            "is_public": False
        }

        create_url = reverse("note-list")
        response = auth_client.post(create_url, data=create_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        note_id = response.data["id"]
        toggle_url = reverse("note-toggle-visibility", args=[note_id])

        # Multiple concurrent toggles
        responses = []
        for _ in range(3):
            response = auth_client.post(toggle_url)
            responses.append(response)

        # All should succeed
        for response in responses:
            assert response.status_code == status.HTTP_200_OK

        # Final state should be public (odd number of toggles)
        detail_url = reverse("note-detail", args=[note_id])
        response = auth_client.get(detail_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_public"] is True


@pytest.mark.django_db
class TestAPIWorkflowsWithExternalServices:
    """Test API workflows that might interact with external services"""

    @pytest.fixture
    def user(self):
        return User.objects.create_user(
            email="external@example.com",
            password="testpass123",
            name="External User",
        )

    @pytest.fixture
    def auth_client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    @patch('apps.api.views.HealthCheckViewSet._check_celery')
    def test_workflow_with_celery_integration(self, mock_celery_check, auth_client):
        """Test workflow when Celery is available"""
        mock_celery_check.return_value = True

        # Health check should include Celery status
        health_url = reverse("health-list")
        response = APIClient().get(health_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["celery"] is True

    @patch('apps.api.views.HealthCheckViewSet._get_system_metrics')
    def test_workflow_with_system_metrics(self, mock_metrics, admin_user):
        """Test workflow with system metrics for staff users"""
        mock_metrics.return_value = {
            "uptime": "24.5 hours",
            "memory_usage": 67.2,
            "cpu_usage": 15.8
        }

        client = APIClient()
        client.force_authenticate(user=admin_user)

        health_url = reverse("health-list")
        response = client.get(health_url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["uptime"] == "24.5 hours"
        assert response.data["memory_usage"] == 67.2
        assert response.data["cpu_usage"] == 15.8

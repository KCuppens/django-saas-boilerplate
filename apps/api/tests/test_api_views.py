from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.api.models import APIKey, Note

User = get_user_model()


class NoteViewSetTestCase(APITestCase):
    """Test NoteViewSet"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create test users
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", name="Other User", password="otherpass123"
        )
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com", name="Admin User", password="adminpass123"
        )

        # Create test notes
        self.user_note = Note.objects.create(
            title="User's Note",
            content="Private note content",
            is_public=False,
            created_by=self.user,
            updated_by=self.user,
        )

        self.public_note = Note.objects.create(
            title="Public Note",
            content="Public note content",
            is_public=True,
            created_by=self.other_user,
            updated_by=self.other_user,
        )

        self.other_private_note = Note.objects.create(
            title="Other's Private Note",
            content="Other's private content",
            is_public=False,
            created_by=self.other_user,
            updated_by=self.other_user,
        )

    def test_list_notes_authenticated_user(self):
        """Test listing notes as authenticated user"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # User should see their own note and public note
        self.assertEqual(len(response.data["results"]), 2)
        note_titles = [note["title"] for note in response.data["results"]]
        self.assertIn("User's Note", note_titles)
        self.assertIn("Public Note", note_titles)
        self.assertNotIn("Other's Private Note", note_titles)

    def test_list_notes_admin_user(self):
        """Test listing notes as admin user"""
        self.client.force_authenticate(user=self.admin_user)

        # Mock the is_admin method
        self.admin_user.is_admin = Mock(return_value=True)

        url = reverse("note-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Admin should see all notes
        self.assertEqual(len(response.data["results"]), 3)

    def test_list_notes_unauthenticated(self):
        """Test listing notes as unauthenticated user"""
        url = reverse("note-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_notes_with_search(self):
        """Test listing notes with search parameter"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-list")

        response = self.client.get(url, {"search": "Public"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "Public Note")

    def test_list_notes_with_tags_filter(self):
        """Test listing notes with tags filter"""
        # Add tags to a note
        self.user_note.tags = "django,testing"
        self.user_note.save()

        self.client.force_authenticate(user=self.user)
        url = reverse("note-list")

        response = self.client.get(url, {"tags": "django"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "User's Note")

    def test_list_notes_with_public_filter(self):
        """Test listing notes with is_public filter"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-list")

        response = self.client.get(url, {"is_public": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "Public Note")

    def test_create_note(self):
        """Test creating a new note"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-list")

        data = {
            "title": "New Note",
            "content": "New note content",
            "is_public": True,
            "tag_list": ["new", "test"],
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "New Note")
        self.assertEqual(response.data["created_by_name"], self.user.get_full_name())

    def test_retrieve_own_note(self):
        """Test retrieving user's own note"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-detail", kwargs={"pk": self.user_note.pk})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "User's Note")

    def test_retrieve_public_note(self):
        """Test retrieving public note"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-detail", kwargs={"pk": self.public_note.pk})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Public Note")

    def test_retrieve_other_private_note_denied(self):
        """Test retrieving other user's private note is denied"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-detail", kwargs={"pk": self.other_private_note.pk})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_own_note(self):
        """Test updating user's own note"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-detail", kwargs={"pk": self.user_note.pk})

        data = {"title": "Updated Note", "content": "Updated content"}

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated Note")

    def test_update_other_note_denied(self):
        """Test updating other user's note is denied"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-detail", kwargs={"pk": self.public_note.pk})

        data = {"title": "Hacked Note"}

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_own_note(self):
        """Test deleting user's own note"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-detail", kwargs={"pk": self.user_note.pk})

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Note.objects.filter(pk=self.user_note.pk).exists())

    def test_my_notes_action(self):
        """Test my_notes custom action"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-my-notes")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "User's Note")

    def test_public_notes_action(self):
        """Test public custom action"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-public")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "Public Note")

    def test_toggle_visibility_action(self):
        """Test toggle_visibility custom action"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-toggle-visibility", kwargs={"pk": self.user_note.pk})

        # Note starts as private
        self.assertFalse(self.user_note.is_public)

        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_public"])

        # Verify in database
        self.user_note.refresh_from_db()
        self.assertTrue(self.user_note.is_public)

    def test_get_serializer_class_for_create(self):
        """Test that create action uses NoteCreateUpdateSerializer"""
        self.client.force_authenticate(user=self.user)

        # Test via actual API call
        url = reverse("note-list")
        data = {"title": "Test", "content": "Content", "tag_list": ["test"]}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class HealthCheckViewSetTestCase(APITestCase):
    """Test HealthCheckViewSet"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )
        self.staff_user = User.objects.create_user(
            email="staff@example.com",
            name="Staff User",
            password="staffpass123",
            is_staff=True,
        )

    def test_health_check_unauthenticated(self):
        """Test health check without authentication"""
        url = reverse("healthcheck-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("status", response.data)
        self.assertIn("timestamp", response.data)
        self.assertIn("database", response.data)
        self.assertIn("cache", response.data)

    def test_health_check_with_staff_user(self):
        """Test health check with staff user gets system metrics"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse("healthcheck-list")

        with (
            patch("psutil.boot_time", return_value=1640995200),
            patch("psutil.virtual_memory") as mock_memory,
            patch("psutil.cpu_percent", return_value=45.0),
        ):
            mock_memory.return_value.percent = 75.0

            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Staff user should get system metrics
            self.assertIn("uptime", response.data)
            self.assertIn("memory_usage", response.data)
            self.assertIn("cpu_usage", response.data)

    @patch("apps.api.views.HealthCheckViewSet._check_database")
    @patch("apps.api.views.HealthCheckViewSet._check_cache")
    def test_health_check_unhealthy(self, mock_cache, mock_db):
        """Test health check when services are unhealthy"""
        mock_db.return_value = False
        mock_cache.return_value = True

        url = reverse("healthcheck-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["status"], "unhealthy")
        self.assertFalse(response.data["database"])

    def test_ready_check_success(self):
        """Test readiness check when all services are ready"""
        url = reverse("healthcheck-ready")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ready")

    @patch("apps.api.views.HealthCheckViewSet._check_database")
    def test_ready_check_database_failure(self, mock_db):
        """Test readiness check when database is unavailable"""
        mock_db.return_value = False

        url = reverse("healthcheck-ready")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["reason"], "database unavailable")

    @patch("apps.api.views.HealthCheckViewSet._check_cache")
    def test_ready_check_cache_failure(self, mock_cache):
        """Test readiness check when cache is unavailable"""
        mock_cache.return_value = False

        url = reverse("healthcheck-ready")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["reason"], "cache unavailable")

    def test_live_check(self):
        """Test liveness check"""
        url = reverse("healthcheck-live")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "alive")
        self.assertIn("timestamp", response.data)

    def test_check_database_success(self):
        """Test database check method directly"""
        viewset = self.get_viewset_instance()
        result = viewset._check_database()
        self.assertTrue(result)

    @patch("django.db.connection")
    def test_check_database_failure(self, mock_connection):
        """Test database check failure"""
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor

        viewset = self.get_viewset_instance()
        result = viewset._check_database()
        self.assertFalse(result)

    def test_check_cache_success(self):
        """Test cache check method directly"""
        viewset = self.get_viewset_instance()
        result = viewset._check_cache()
        self.assertTrue(result)

    @patch("django.core.cache.cache")
    def test_check_cache_failure(self, mock_cache):
        """Test cache check failure"""
        mock_cache.set.side_effect = Exception("Cache error")

        viewset = self.get_viewset_instance()
        result = viewset._check_cache()
        self.assertFalse(result)

    @patch("celery.current_app")
    def test_check_celery_success(self, mock_app):
        """Test Celery check success"""
        mock_inspect = Mock()
        mock_inspect.stats.return_value = {"worker1": {}}
        mock_app.control.inspect.return_value = mock_inspect

        viewset = self.get_viewset_instance()
        result = viewset._check_celery()
        self.assertTrue(result)

    @patch("celery.current_app")
    def test_check_celery_failure(self, mock_app):
        """Test Celery check failure"""
        mock_app.control.inspect.side_effect = Exception("Celery error")

        viewset = self.get_viewset_instance()
        result = viewset._check_celery()
        self.assertIsNone(result)

    def test_get_version(self):
        """Test version retrieval"""
        viewset = self.get_viewset_instance()
        version = viewset._get_version()
        self.assertEqual(version, "1.0.0")

    def test_get_system_metrics_no_psutil(self):
        """Test system metrics when psutil is not available"""
        viewset = self.get_viewset_instance()
        
        # Remove psutil from sys.modules if it exists
        import sys
        psutil_backup = sys.modules.pop('psutil', None)
        
        # Make sure importing psutil raises ImportError
        sys.modules['psutil'] = None
        
        try:
            metrics = viewset._get_system_metrics()
            self.assertEqual(metrics, {})
        finally:
            # Restore psutil
            if psutil_backup is not None:
                sys.modules['psutil'] = psutil_backup
            elif 'psutil' in sys.modules:
                del sys.modules['psutil']

    def get_viewset_instance(self):
        """Get HealthCheckViewSet instance"""
        from django.test import RequestFactory

        from apps.api.views import HealthCheckViewSet

        factory = RequestFactory()
        request = factory.get("/")
        viewset = HealthCheckViewSet()
        viewset.request = request
        return viewset


class APIKeyViewSetTestCase(APITestCase):
    """Test APIKeyViewSet"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", name="Other User", password="otherpass123"
        )

        self.api_key = APIKey.objects.create(
            name="Test Key", permissions=["read"], user=self.user
        )

        self.other_api_key = APIKey.objects.create(
            name="Other Key", permissions=["read", "write"], user=self.other_user
        )

    def test_list_api_keys_authenticated(self):
        """Test listing API keys for authenticated user"""
        self.client.force_authenticate(user=self.user)
        url = reverse("apikey-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Test Key")

    def test_list_api_keys_unauthenticated(self):
        """Test listing API keys without authentication"""
        url = reverse("apikey-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_api_key(self):
        """Test creating new API key"""
        self.client.force_authenticate(user=self.user)
        url = reverse("apikey-list")

        data = {
            "name": "New API Key",
            "permissions": ["read", "write"],
            "is_active": True,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New API Key")
        self.assertIn("key", response.data)

    def test_retrieve_own_api_key(self):
        """Test retrieving user's own API key"""
        self.client.force_authenticate(user=self.user)
        url = reverse("apikey-detail", kwargs={"pk": self.api_key.pk})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Key")

    def test_retrieve_other_api_key_denied(self):
        """Test retrieving other user's API key is denied"""
        self.client.force_authenticate(user=self.user)
        url = reverse("apikey-detail", kwargs={"pk": self.other_api_key.pk})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_api_key(self):
        """Test updating API key"""
        self.client.force_authenticate(user=self.user)
        url = reverse("apikey-detail", kwargs={"pk": self.api_key.pk})

        data = {"name": "Updated Key", "is_active": False}

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Key")
        self.assertFalse(response.data["is_active"])

    def test_delete_api_key(self):
        """Test deleting API key"""
        self.client.force_authenticate(user=self.user)
        url = reverse("apikey-detail", kwargs={"pk": self.api_key.pk})

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(APIKey.objects.filter(pk=self.api_key.pk).exists())

    def test_get_serializer_class_for_create(self):
        """Test that create action uses APIKeyCreateSerializer"""
        self.client.force_authenticate(user=self.user)
        url = reverse("apikey-list")

        data = {"name": "Test Create", "permissions": ["read"]}

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("key", response.data)  # Only create serializer returns the key

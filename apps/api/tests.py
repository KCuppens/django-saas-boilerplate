from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from apps.api.models import Note

User = get_user_model()


class NoteModelTest(APITestCase):
    """Test Note model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )

    def test_create_note(self):
        """Test note creation"""
        note = Note.objects.create(
            title="Test Note",
            content="This is a test note",
            created_by=self.user,
            updated_by=self.user,
        )

        self.assertEqual(note.title, "Test Note")
        self.assertEqual(note.created_by, self.user)
        self.assertFalse(note.is_public)

    def test_note_string_representation(self):
        """Test note string representation"""
        note = Note(title="Test Note")
        self.assertEqual(str(note), "Test Note")

    def test_tag_list_property(self):
        """Test tag_list property"""
        note = Note(tags="tag1, tag2, tag3")
        self.assertEqual(note.tag_list, ["tag1", "tag2", "tag3"])


class NoteAPITest(APITestCase):
    """Test Note API endpoints"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        self.note = Note.objects.create(
            title="Test Note",
            content="Test content",
            created_by=self.user,
            updated_by=self.user,
        )

    def test_list_notes_authenticated(self):
        """Test listing notes for authenticated user"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_create_note(self):
        """Test creating a new note"""
        self.client.force_authenticate(user=self.user)
        url = reverse("note-list")
        data = {
            "title": "New Note",
            "content": "New content",
            "tag_list": ["test", "api"],
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Note.objects.filter(title="New Note").exists())

    def test_list_notes_unauthenticated(self):
        """Test listing notes for unauthenticated user"""
        url = reverse("note-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class HealthCheckAPITest(APITestCase):
    """Test Health Check API endpoints"""

    def test_health_check(self):
        """Test health check endpoint"""
        url = reverse("health-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "healthy")
        self.assertTrue("timestamp" in response.data)

    def test_readiness_check(self):
        """Test readiness check endpoint"""
        url = reverse("health-ready")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ready")

    def test_liveness_check(self):
        """Test liveness check endpoint"""
        url = reverse("health-live")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "alive")

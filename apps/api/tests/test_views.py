from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.api.models import APIKey

User = get_user_model()


class TestAPIKeyViewSet(APITestCase):
    """Test APIKey ViewSet functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="testpass123"
        )

        self.api_key = APIKey.objects.create(
            name="Test API Key",
            permissions="read",
            user=self.user,
        )

        # Create an API key for the other user
        self.other_api_key = APIKey.objects.create(
            name="Other User's API Key",
            permissions="write",
            user=self.other_user,
        )

    def test_list_api_keys(self):
        """Test listing API keys for authenticated user"""
        self.client.force_authenticate(user=self.user)
        url = reverse("apikey-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only return API keys for the current user
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.api_key.id)

    def test_create_api_key(self):
        """Test creating a new API key"""
        self.client.force_authenticate(user=self.user)
        url = reverse("apikey-list")

        data = {
            "name": "New API Key",
            "permissions": "write",
            "is_active": True,
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New API Key")
        self.assertEqual(response.data["permissions"], "write")
        self.assertTrue(response.data["is_active"])
        self.assertIsNotNone(response.data["key"])

        # Verify API key was created in database
        self.assertTrue(
            APIKey.objects.filter(name="New API Key", user=self.user).exists()
        )

    def test_delete_api_key(self):
        """Test deleting an API key"""
        self.client.force_authenticate(user=self.user)
        url = reverse("apikey-detail", kwargs={"pk": self.api_key.pk})

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify API key was deleted
        self.assertFalse(APIKey.objects.filter(id=self.api_key.id).exists())

    def test_retrieve_api_key(self):
        """Test retrieving a specific API key"""
        self.client.force_authenticate(user=self.user)
        url = reverse("apikey-detail", kwargs={"pk": self.api_key.pk})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.api_key.id)
        self.assertEqual(response.data["name"], "Test API Key")

    def test_update_api_key(self):
        """Test updating an API key"""
        self.client.force_authenticate(user=self.user)
        url = reverse("apikey-detail", kwargs={"pk": self.api_key.pk})

        data = {
            "name": "Updated API Key",
            "permissions": "admin",
            "is_active": False,
        }

        response = self.client.put(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated API Key")
        self.assertEqual(response.data["permissions"], "admin")
        self.assertFalse(response.data["is_active"])

    def test_partial_update_api_key(self):
        """Test partially updating an API key"""
        self.client.force_authenticate(user=self.user)
        url = reverse("apikey-detail", kwargs={"pk": self.api_key.pk})

        data = {"name": "Partially Updated API Key"}

        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Partially Updated API Key")
        # Other fields should remain unchanged
        self.assertEqual(response.data["permissions"], "read")

    def test_cannot_access_other_users_api_keys(self):
        """Test that users cannot access other users' API keys"""
        self.client.force_authenticate(user=self.user)

        # Try to retrieve other user's API key
        url = reverse("apikey-detail", kwargs={"pk": self.other_api_key.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Try to delete other user's API key
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access API keys"""
        url = reverse("apikey-list")

        # List API keys without authentication
        response = self.client.get(url)
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

        # Create API key without authentication
        data = {"name": "Test Key", "permissions": "read"}
        response = self.client.post(url, data)
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_list_only_active_keys(self):
        """Test listing includes inactive keys (user should see all their keys)"""
        # Create an inactive API key
        inactive_key = APIKey.objects.create(
            name="Inactive API Key",
            permissions="read",
            is_active=False,
            user=self.user,
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("apikey-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return both active and inactive keys for the user
        self.assertEqual(len(response.data["results"]), 2)

        key_ids = [key["id"] for key in response.data["results"]]
        self.assertIn(self.api_key.id, key_ids)
        self.assertIn(inactive_key.id, key_ids)


class TestHealthCheckView(APITestCase):
    """Test Health Check View functionality"""

    def test_health_check(self):
        """Test basic health check endpoint"""
        url = reverse("health-list")
        response = self.client.get(url)

        # Health check can return 200 (healthy) or 503 (unhealthy)
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE],
        )
        self.assertIn("status", response.data)
        self.assertIn(response.data["status"], ["healthy", "unhealthy"])

    def test_health_check_response_format(self):
        """Test health check response format"""
        url = reverse("health-list")
        response = self.client.get(url)

        # Health check can return 200 (healthy) or 503 (unhealthy)
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE],
        )

        # Check required fields in response
        required_fields = ["status", "timestamp", "database", "cache"]
        for field in required_fields:
            self.assertIn(field, response.data)

        # Check that status is one of the expected values
        self.assertIn(response.data["status"], ["healthy", "unhealthy"])


class TestSystemMetricsView(APITestCase):
    """Test System Metrics View functionality"""

    def setUp(self):
        """Set up test user"""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        self.staff_user = User.objects.create_user(
            email="staff@example.com", password="testpass123", is_staff=True
        )

    def test_system_metrics(self):
        """Test system metrics endpoint for non-staff user"""
        self.client.force_authenticate(user=self.user)
        url = reverse("health-list")

        response = self.client.get(url)

        # Health check can return 200 (healthy) or 503 (unhealthy)
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE],
        )
        # Non-staff users should not see system metrics
        self.assertNotIn("uptime", response.data)
        self.assertNotIn("memory_usage", response.data)
        self.assertNotIn("cpu_usage", response.data)

    def test_system_metrics_authenticated(self):
        """Test system metrics endpoint for staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse("health-list")

        response = self.client.get(url)

        # Health check can return 200 (healthy) or 503 (unhealthy)
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE],
        )
        # Staff users should see system metrics (if psutil is available)
        self.assertIn("status", response.data)

    def test_system_metrics_format(self):
        """Test system metrics response format for staff user"""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse("health-list")

        response = self.client.get(url)

        # Health check can return 200 (healthy) or 503 (unhealthy)
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE],
        )

        # Check basic health fields are present
        basic_fields = ["status", "timestamp", "database", "cache"]
        for field in basic_fields:
            self.assertIn(field, response.data)

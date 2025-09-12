from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.api.models import APIKey
from apps.api.serializers import APIKeyCreateSerializer, APIKeySerializer

User = get_user_model()


class TestAPIKeySerializer(TestCase):
    """Test APIKey serializer functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )
        self.api_key = APIKey.objects.create(
            name="Test API Key",
            permissions="read",
            user=self.user,
        )
        
        # Create a request factory for context
        self.factory = APIRequestFactory()

    def test_serializer_fields(self):
        """Test serializer has expected fields"""
        serializer = APIKeySerializer(instance=self.api_key)
        data = serializer.data
        
        expected_fields = [
            "id", "name", "key", "permissions", "is_active", 
            "user", "last_used", "created_at", "updated_at"
        ]
        
        for field in expected_fields:
            self.assertIn(field, data)

    def test_serializer_data(self):
        """Test serializer data output"""
        serializer = APIKeySerializer(instance=self.api_key)
        data = serializer.data
        
        self.assertEqual(data["name"], "Test API Key")
        self.assertEqual(data["permissions"], "read")
        self.assertTrue(data["is_active"])
        self.assertEqual(data["user"], self.user.id)
        self.assertIsNotNone(data["key"])

    def test_create_api_key(self):
        """Test creating API key via serializer"""
        # Create a mock request with user
        request = self.factory.post("/")
        request.user = self.user
        
        data = {
            "name": "New API Key",
            "permissions": "write",
            "is_active": True,
        }
        
        # Use the raw request object directly instead of wrapping it
        serializer = APIKeyCreateSerializer(
            data=data, 
            context={"request": request}
        )
        self.assertTrue(serializer.is_valid())
        
        api_key = serializer.save()
        self.assertEqual(api_key.name, "New API Key")
        self.assertEqual(api_key.permissions, "write")
        self.assertTrue(api_key.is_active)
        self.assertEqual(api_key.user, self.user)
        self.assertIsNotNone(api_key.key)

    def test_serializer_readonly_fields(self):
        """Test that read-only fields cannot be updated"""
        serializer = APIKeySerializer(instance=self.api_key)
        
        readonly_fields = ["id", "key", "user", "last_used", "created_at", "updated_at"]
        
        for field in readonly_fields:
            self.assertIn(field, serializer.fields)
            self.assertTrue(serializer.fields[field].read_only)

    def test_create_serializer_fields(self):
        """Test create serializer has correct fields"""
        data = {
            "name": "Test Key",
            "permissions": "read",
            "is_active": True,
        }
        
        request = self.factory.post("/")
        request.user = self.user
        
        serializer = APIKeyCreateSerializer(
            data=data,
            context={"request": Request(request)}
        )
        
        expected_fields = ["name", "permissions", "is_active"]
        
        for field in expected_fields:
            self.assertIn(field, serializer.fields)
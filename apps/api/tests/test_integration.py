from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserProfile
from apps.api.models import APIKey, Note

User = get_user_model()


class TestAPIIntegration(APITestCase):
    """Integration tests for API functionality"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="integration@example.com",
            password="integrationpass123",
            name="Integration User"
        )
        
        # Create user profile
        self.profile, _ = UserProfile.objects.get_or_create(
            user=self.user,
            defaults={
                'bio': 'Test bio',
                'location': 'Test location'
            }
        )

    def test_complete_user_flow(self):
        """Test complete user workflow from registration to API usage"""
        # Test user registration
        registration_data = {
            'email': 'newuser@example.com',
            'name': 'New User',
            'password1': 'newuserpass123',
            'password2': 'newuserpass123'
        }
        
        register_url = reverse('user-register')
        response = self.client.post(register_url, registration_data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)
        self.assertIn('id', response.data['user'])  # Check for id field
        
        # Get the new user
        new_user = User.objects.get(email='newuser@example.com')
        self.client.force_authenticate(user=new_user)
        
        # Test user profile retrieval
        profile_url = reverse('user-detail', args=[new_user.id])
        response = self.client.get(profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)  # Check for id field
        self.assertEqual(response.data['email'], 'newuser@example.com')
        
        # Test API key creation
        api_key_url = reverse('apikey-list')
        key_data = {
            'name': 'Integration Test Key',
            'permissions': 'write'
        }
        
        response = self.client.post(api_key_url, key_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)  # Check for id field
        self.assertIn('key', response.data)
        
        # Test note creation with the authenticated user
        note_url = reverse('note-list')
        note_data = {
            'title': 'Integration Test Note',
            'content': 'This is a test note created during integration testing',
            'tag_list': ['integration', 'test']
        }
        
        response = self.client.post(note_url, note_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)  # Check for id field
        self.assertEqual(response.data['title'], 'Integration Test Note')

    def test_user_profile_flow(self):
        """Test user profile retrieval and update flow"""
        self.client.force_authenticate(user=self.user)
        
        # Test profile retrieval
        profile_url = reverse('user-detail', args=[self.user.id])
        response = self.client.get(profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)  # Check for id field
        self.assertEqual(response.data['email'], self.user.email)
        self.assertIn('profile', response.data)
        
        # Test profile update
        update_data = {
            'name': 'Updated Integration User',
            'profile': {
                'bio': 'Updated bio',
                'location': 'Updated location'
            }
        }
        
        response = self.client.patch(profile_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)  # Check for id field
        self.assertEqual(response.data['name'], 'Updated Integration User')
        
        # Verify the update persisted
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, 'Updated Integration User')

    def test_subscription_flow(self):
        """Test subscription-related workflow (mocked since no subscription model exists)"""
        self.client.force_authenticate(user=self.user)
        
        # Test user profile access (as a proxy for subscription info)
        profile_url = reverse('user-detail', args=[self.user.id])
        response = self.client.get(profile_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)  # Check for id field
        
        # Test creating premium content (private notes as subscription feature)
        note_url = reverse('note-list')
        premium_note_data = {
            'title': 'Premium Feature Note',
            'content': 'This note uses premium features',
            'is_public': False,  # Private notes as premium feature
            'tag_list': ['premium', 'subscription']
        }
        
        response = self.client.post(note_url, premium_note_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)  # Check for id field
        self.assertFalse(response.data['is_public'])
        
        # Test API key management (as subscription feature)
        api_key_url = reverse('apikey-list')
        api_key_data = {
            'name': 'Subscription API Key',
            'permissions': 'admin'  # Admin permissions as premium feature
        }
        
        response = self.client.post(api_key_url, api_key_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)  # Check for id field
        self.assertEqual(response.data['permissions'], 'admin')

    def test_api_error_handling(self):
        """Test API error responses and error handling"""
        
        # Test unauthenticated access
        note_url = reverse('note-list')
        response = self.client.get(note_url)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        
        # Test authenticated user
        self.client.force_authenticate(user=self.user)
        
        # Test invalid note creation
        invalid_note_data = {
            'title': '',  # Empty title should cause validation error
            'content': 'Test content'
        }
        
        response = self.client.post(note_url, invalid_note_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test accessing non-existent note
        non_existent_url = reverse('note-detail', args=[99999])
        response = self.client.get(non_existent_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # Test invalid API key creation
        api_key_url = reverse('apikey-list')
        invalid_key_data = {
            'name': '',  # Empty name should cause validation error
            'permissions': 'invalid_permission'
        }
        
        response = self.client.post(api_key_url, invalid_key_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test valid API key creation to ensure we get id field
        valid_key_data = {
            'name': 'Valid Test Key',
            'permissions': 'read'
        }
        
        response = self.client.post(api_key_url, valid_key_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)  # Check for id field
        
        # Test health check endpoint
        health_url = reverse('health-list')
        response = self.client.get(health_url)
        # Health check might return 503 if services like Celery are unavailable in test environment
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])
        # Health check might not have an id field, so we check for status
        self.assertIn('status', response.data)

    def test_note_crud_operations(self):
        """Test complete CRUD operations for notes"""
        self.client.force_authenticate(user=self.user)
        
        # Create note
        note_url = reverse('note-list')
        note_data = {
            'title': 'CRUD Test Note',
            'content': 'Testing CRUD operations',
            'tag_list': ['crud', 'test']
        }
        
        response = self.client.post(note_url, note_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)  # Check for id field
        note_id = response.data['id']
        
        # Read note
        detail_url = reverse('note-detail', args=[note_id])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)  # Check for id field
        self.assertEqual(response.data['title'], 'CRUD Test Note')
        
        # Update note
        update_data = {
            'title': 'Updated CRUD Test Note',
            'content': 'Updated content for CRUD testing'
        }
        
        response = self.client.patch(detail_url, update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)  # Check for id field
        self.assertEqual(response.data['title'], 'Updated CRUD Test Note')
        
        # Delete note
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deletion
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_key_management(self):
        """Test API key management operations"""
        self.client.force_authenticate(user=self.user)
        
        # Create API key
        api_key_url = reverse('apikey-list')
        key_data = {
            'name': 'Management Test Key',
            'permissions': 'write',
            'is_active': True
        }
        
        response = self.client.post(api_key_url, key_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)  # Check for id field
        self.assertIn('key', response.data)
        key_id = response.data['id']
        
        # List API keys
        response = self.client.get(api_key_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)
        
        # Update API key
        detail_url = reverse('apikey-detail', args=[key_id])
        update_data = {
            'name': 'Updated Management Test Key',
            'is_active': False
        }
        
        response = self.client.patch(detail_url, update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)  # Check for id field
        self.assertEqual(response.data['name'], 'Updated Management Test Key')
        self.assertFalse(response.data['is_active'])
        
        # Delete API key
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
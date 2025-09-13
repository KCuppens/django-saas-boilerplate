"""Comprehensive tests for file management functionality."""

import tempfile
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.core.enums import FileType
from apps.files.models import FileUpload
from apps.files.services import FileService

User = get_user_model()


class FileUploadModelTestCase(TestCase):
    """Test FileUpload model functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="adminpass123",
            name="Admin User",
            is_staff=True,
            is_superuser=True,
        )

    def test_file_upload_creation(self):
        """Test creating a file upload record."""
        file_upload = FileUpload.objects.create(
            original_filename="test.pdf",
            filename="unique_test.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/unique_test.pdf",
            is_public=False,
            created_by=self.user,
            updated_by=self.user,
        )

        self.assertEqual(file_upload.original_filename, "test.pdf")
        self.assertEqual(file_upload.file_type, FileType.DOCUMENT)
        self.assertEqual(file_upload.created_by, self.user)
        self.assertFalse(file_upload.is_public)

    def test_file_upload_str_representation(self):
        """Test FileUpload string representation."""
        file_upload = FileUpload.objects.create(
            original_filename="test_document.pdf",
            filename="unique_test.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/unique_test.pdf",
            created_by=self.user,
            updated_by=self.user,
        )

        self.assertEqual(str(file_upload), "test_document.pdf")

    def test_file_size_human_property(self):
        """Test human readable file size property."""
        file_upload = FileUpload.objects.create(
            original_filename="test.pdf",
            filename="unique_test.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,  # 1KB
            storage_path="uploads/test/unique_test.pdf",
            created_by=self.user,
            updated_by=self.user,
        )

        # Test that the property exists and returns a string
        human_size = file_upload.file_size_human
        self.assertIsInstance(human_size, str)

    def test_file_expiration(self):
        """Test file expiration functionality."""
        # Test non-expired file
        future_time = timezone.now() + timedelta(hours=1)
        file_upload = FileUpload.objects.create(
            original_filename="test.pdf",
            filename="unique_test.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/unique_test.pdf",
            expires_at=future_time,
            created_by=self.user,
            updated_by=self.user,
        )
        self.assertFalse(file_upload.is_expired)

        # Test expired file
        past_time = timezone.now() - timedelta(hours=1)
        file_upload.expires_at = past_time
        file_upload.save()
        self.assertTrue(file_upload.is_expired)

        # Test file without expiration
        file_upload.expires_at = None
        file_upload.save()
        self.assertFalse(file_upload.is_expired)

    def test_file_type_properties(self):
        """Test file type checking properties."""
        # Test image file
        image_file = FileUpload.objects.create(
            original_filename="test.jpg",
            filename="unique_test.jpg",
            file_type=FileType.IMAGE,
            mime_type="image/jpeg",
            file_size=1024,
            storage_path="uploads/test/unique_test.jpg",
            created_by=self.user,
            updated_by=self.user,
        )
        self.assertTrue(image_file.is_image)
        self.assertFalse(image_file.is_document)

        # Test document file
        doc_file = FileUpload.objects.create(
            original_filename="test.pdf",
            filename="unique_test.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/unique_test.pdf",
            created_by=self.user,
            updated_by=self.user,
        )
        self.assertFalse(doc_file.is_image)
        self.assertTrue(doc_file.is_document)

    def test_file_access_permissions(self):
        """Test file access permission logic."""
        # Create different types of files
        private_file = FileUpload.objects.create(
            original_filename="private.pdf",
            filename="private.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/private.pdf",
            is_public=False,
            created_by=self.user,
            updated_by=self.user,
        )

        public_file = FileUpload.objects.create(
            original_filename="public.pdf",
            filename="public.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/public.pdf",
            is_public=True,
            created_by=self.user,
            updated_by=self.user,
        )

        expired_public_file = FileUpload.objects.create(
            original_filename="expired.pdf",
            filename="expired.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/expired.pdf",
            is_public=True,
            expires_at=timezone.now() - timedelta(hours=1),
            created_by=self.user,
            updated_by=self.user,
        )

        # Test owner access
        self.assertTrue(private_file.can_access(self.user))
        self.assertTrue(public_file.can_access(self.user))
        self.assertTrue(
            expired_public_file.can_access(self.user)
        )  # Owner can access expired files

        # Test different user access
        other_user = User.objects.create_user(
            email="other@example.com", password="otherpass123", name="Other User"
        )
        self.assertFalse(private_file.can_access(other_user))
        self.assertTrue(public_file.can_access(other_user))
        self.assertFalse(expired_public_file.can_access(other_user))

        # Test anonymous access
        self.assertFalse(private_file.can_access(None))
        self.assertTrue(public_file.can_access(None))
        self.assertFalse(expired_public_file.can_access(None))

        # Test admin access
        self.assertTrue(private_file.can_access(self.admin_user))
        self.assertTrue(public_file.can_access(self.admin_user))
        self.assertTrue(expired_public_file.can_access(self.admin_user))

    def test_increment_download_count(self):
        """Test download counter increment."""
        file_upload = FileUpload.objects.create(
            original_filename="test.pdf",
            filename="unique_test.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/unique_test.pdf",
            created_by=self.user,
            updated_by=self.user,
        )

        initial_count = file_upload.download_count
        file_upload.increment_download_count()
        file_upload.refresh_from_db()

        self.assertEqual(file_upload.download_count, initial_count + 1)


class FileServiceTestCase(TestCase):
    """Test FileService functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

    def test_file_type_mapping(self):
        """Test file type mapping functionality."""
        # Test known MIME types
        self.assertEqual(FileService.FILE_TYPE_MAP["image/jpeg"], FileType.IMAGE)
        self.assertEqual(
            FileService.FILE_TYPE_MAP["application/pdf"], FileType.DOCUMENT
        )
        self.assertEqual(FileService.FILE_TYPE_MAP["video/mp4"], FileType.VIDEO)
        self.assertEqual(FileService.FILE_TYPE_MAP["audio/mpeg"], FileType.AUDIO)
        self.assertEqual(FileService.FILE_TYPE_MAP["application/zip"], FileType.ARCHIVE)

    @patch("apps.files.services.default_storage")
    def test_upload_file_success(self, mock_storage):
        """Test successful file upload."""
        # Mock storage operations
        mock_storage.save.return_value = "uploads/1/test_file.pdf"

        # Create test file
        file_content = b"Test PDF content"
        test_file = SimpleUploadedFile(
            "test.pdf", file_content, content_type="application/pdf"
        )
        test_file.size = len(file_content)

        # Upload file
        file_upload = FileService.upload_file(
            file=test_file,
            user=self.user,
            description="Test upload",
            tags="test,upload",
            is_public=True,
        )

        # Verify file upload record
        self.assertIsInstance(file_upload, FileUpload)
        self.assertEqual(file_upload.original_filename, "test.pdf")
        self.assertEqual(file_upload.file_type, FileType.DOCUMENT)
        self.assertEqual(file_upload.mime_type, "application/pdf")
        self.assertEqual(file_upload.file_size, len(file_content))
        self.assertEqual(file_upload.description, "Test upload")
        self.assertEqual(file_upload.tags, "test,upload")
        self.assertTrue(file_upload.is_public)
        self.assertEqual(file_upload.created_by, self.user)

        # Verify storage was called
        mock_storage.save.assert_called_once()

    def test_file_validation_success(self):
        """Test successful file validation."""
        file_content = b"Test PDF content"
        test_file = SimpleUploadedFile(
            "test.pdf", file_content, content_type="application/pdf"
        )
        test_file.size = len(file_content)

        validation = FileService.validate_file(test_file, max_size_mb=10)

        self.assertTrue(validation["valid"])
        self.assertEqual(len(validation["errors"]), 0)
        self.assertEqual(validation["file_type"], FileType.DOCUMENT)
        self.assertEqual(validation["mime_type"], "application/pdf")

    def test_file_validation_size_error(self):
        """Test file validation with size error."""
        # Create large file content
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        test_file = SimpleUploadedFile(
            "large.pdf", large_content, content_type="application/pdf"
        )
        test_file.size = len(large_content)

        validation = FileService.validate_file(test_file, max_size_mb=10)

        self.assertFalse(validation["valid"])
        self.assertGreater(len(validation["errors"]), 0)
        self.assertIn("exceeds maximum", validation["errors"][0])

    def test_file_validation_extension_error(self):
        """Test file validation with disallowed extension."""
        file_content = b"Executable content"
        test_file = SimpleUploadedFile(
            "malicious.exe", file_content, content_type="application/octet-stream"
        )
        test_file.size = len(file_content)

        validation = FileService.validate_file(test_file)

        self.assertFalse(validation["valid"])
        self.assertGreater(len(validation["errors"]), 0)
        self.assertTrue(any("not allowed" in error for error in validation["errors"]))

    def test_file_validation_dangerous_extension(self):
        """Test file validation with dangerous extension."""
        file_content = b"Script content"
        test_file = SimpleUploadedFile(
            "script.js", file_content, content_type="application/javascript"
        )
        test_file.size = len(file_content)

        validation = FileService.validate_file(test_file)

        self.assertFalse(validation["valid"])
        self.assertGreater(len(validation["errors"]), 0)
        self.assertTrue(
            any("security reasons" in error for error in validation["errors"])
        )

    @patch("apps.files.services.default_storage")
    def test_delete_file_success(self, mock_storage):
        """Test successful file deletion."""
        mock_storage.exists.return_value = True
        mock_storage.delete.return_value = True

        file_upload = FileUpload.objects.create(
            original_filename="test.pdf",
            filename="unique_test.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/unique_test.pdf",
            created_by=self.user,
            updated_by=self.user,
        )

        result = FileService.delete_file(file_upload)

        self.assertTrue(result)
        mock_storage.exists.assert_called_once_with(file_upload.storage_path)
        mock_storage.delete.assert_called_once_with(file_upload.storage_path)

        # Verify file was deleted from database
        self.assertFalse(FileUpload.objects.filter(id=file_upload.id).exists())

    @patch("apps.files.services.default_storage")
    def test_delete_file_storage_error(self, mock_storage):
        """Test file deletion with storage error."""
        mock_storage.exists.return_value = True
        mock_storage.delete.side_effect = Exception("Storage error")

        file_upload = FileUpload.objects.create(
            original_filename="test.pdf",
            filename="unique_test.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/unique_test.pdf",
            created_by=self.user,
            updated_by=self.user,
        )

        result = FileService.delete_file(file_upload)

        self.assertFalse(result)
        # File should still exist in database
        self.assertTrue(FileUpload.objects.filter(id=file_upload.id).exists())

    def test_cleanup_expired_files(self):
        """Test cleanup of expired files."""
        # Create expired file
        expired_file = FileUpload.objects.create(
            original_filename="expired.pdf",
            filename="expired.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/expired.pdf",
            expires_at=timezone.now() - timedelta(hours=1),
            created_by=self.user,
            updated_by=self.user,
        )

        # Create non-expired file
        FileUpload.objects.create(
            original_filename="active.pdf",
            filename="active.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/active.pdf",
            expires_at=timezone.now() + timedelta(hours=1),
            created_by=self.user,
            updated_by=self.user,
        )

        with patch.object(FileService, "delete_file", return_value=True) as mock_delete:
            result = FileService.cleanup_expired_files()

            self.assertEqual(result["deleted"], 1)
            self.assertEqual(result["errors"], 0)
            mock_delete.assert_called_once_with(expired_file)

    @patch("apps.files.services.default_storage")
    def test_get_download_url_public_file(self, mock_storage):
        """Test getting download URL for public file."""
        mock_storage.url.return_value = "https://example.com/file.pdf"

        file_upload = FileUpload.objects.create(
            original_filename="public.pdf",
            filename="public.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/public.pdf",
            is_public=True,
            created_by=self.user,
            updated_by=self.user,
        )

        # Mock hasattr to return True for url method
        with patch("builtins.hasattr", return_value=True):
            download_url = FileService.get_download_url(file_upload)

            self.assertEqual(download_url, "https://example.com/file.pdf")
            mock_storage.url.assert_called_once_with(file_upload.storage_path)

    def test_get_upload_url_fallback(self):
        """Test getting upload URL fallback."""
        storage_path = "uploads/test/new_file.pdf"

        # Test fallback when storage doesn't support presigned URLs
        upload_data = FileService.get_upload_url(storage_path)

        self.assertIn("url", upload_data)
        self.assertIn("fields", upload_data)
        self.assertEqual(upload_data["fields"], {})


class FileUploadAPITestCase(APITestCase):
    """Test FileUpload API endpoints."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="otherpass123", name="Other User"
        )

        # Create test files
        self.private_file = FileUpload.objects.create(
            original_filename="private.pdf",
            filename="private.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/private.pdf",
            is_public=False,
            created_by=self.user,
            updated_by=self.user,
        )

        self.public_file = FileUpload.objects.create(
            original_filename="public.pdf",
            filename="public.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/public.pdf",
            is_public=True,
            created_by=self.user,
            updated_by=self.user,
        )

    def test_list_files_authenticated(self):
        """Test listing files when authenticated."""
        self.client.force_authenticate(user=self.user)
        url = reverse("fileupload-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # User should see their own files and public files
        file_ids = [f["id"] for f in response.data["results"]]
        self.assertIn(str(self.private_file.id), file_ids)
        self.assertIn(str(self.public_file.id), file_ids)

    def test_list_files_other_user(self):
        """Test listing files as different user."""
        self.client.force_authenticate(user=self.other_user)
        url = reverse("fileupload-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Other user should only see public files
        file_ids = [f["id"] for f in response.data["results"]]
        self.assertNotIn(str(self.private_file.id), file_ids)
        self.assertIn(str(self.public_file.id), file_ids)

    def test_list_files_unauthenticated(self):
        """Test listing files when not authenticated."""
        url = reverse("fileupload-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("apps.files.services.FileService.upload_file")
    @patch("apps.files.services.FileService.validate_file")
    def test_upload_file_success(self, mock_validate, mock_upload):
        """Test successful file upload."""
        # Mock validation and upload
        mock_validate.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_upload.return_value = self.private_file

        self.client.force_authenticate(user=self.user)
        url = reverse("fileupload-list")

        file_content = b"Test PDF content"
        test_file = SimpleUploadedFile(
            "test.pdf", file_content, content_type="application/pdf"
        )

        data = {"file": test_file, "description": "Test upload", "is_public": False}

        response = self.client.post(url, data, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_validate.assert_called_once()
        mock_upload.assert_called_once()

    @patch("apps.files.services.FileService.validate_file")
    def test_upload_file_validation_error(self, mock_validate):
        """Test file upload with validation error."""
        # Mock validation failure
        mock_validate.return_value = {
            "valid": False,
            "errors": ["File too large"],
            "warnings": [],
        }

        self.client.force_authenticate(user=self.user)
        url = reverse("fileupload-list")

        file_content = b"Large file content"
        test_file = SimpleUploadedFile(
            "large.pdf", file_content, content_type="application/pdf"
        )

        data = {"file": test_file}

        response = self.client.post(url, data, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    def test_retrieve_file_owner(self):
        """Test retrieving file as owner."""
        self.client.force_authenticate(user=self.user)
        url = reverse("fileupload-detail", kwargs={"pk": self.private_file.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.private_file.id))

    def test_retrieve_file_other_user_private(self):
        """Test retrieving private file as different user."""
        self.client.force_authenticate(user=self.other_user)
        url = reverse("fileupload-detail", kwargs={"pk": self.private_file.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_file_other_user_public(self):
        """Test retrieving public file as different user."""
        self.client.force_authenticate(user=self.other_user)
        url = reverse("fileupload-detail", kwargs={"pk": self.public_file.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.public_file.id))

    def test_delete_file_owner(self):
        """Test deleting file as owner."""
        self.client.force_authenticate(user=self.user)
        url = reverse("fileupload-detail", kwargs={"pk": self.private_file.id})

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_file_other_user(self):
        """Test deleting file as different user."""
        self.client.force_authenticate(user=self.other_user)
        url = reverse("fileupload-detail", kwargs={"pk": self.private_file.id})

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_url_endpoint(self):
        """Test getting download URL endpoint."""
        self.client.force_authenticate(user=self.user)
        url = reverse("fileupload-download-url", kwargs={"pk": self.private_file.id})

        with patch.object(
            self.private_file,
            "get_download_url",
            return_value="https://example.com/download",
        ):
            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("download_url", response.data)
            self.assertIn("expires_in", response.data)
            self.assertIn("filename", response.data)

    def test_download_url_access_denied(self):
        """Test download URL endpoint with access denied."""
        self.client.force_authenticate(user=self.other_user)
        url = reverse("fileupload-download-url", kwargs={"pk": self.private_file.id})

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_my_files_endpoint(self):
        """Test my files endpoint."""
        self.client.force_authenticate(user=self.user)
        url = reverse("fileupload-my-files")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should include both files since user is the owner
        file_ids = [f["id"] for f in response.data["results"]]
        self.assertIn(str(self.private_file.id), file_ids)
        self.assertIn(str(self.public_file.id), file_ids)

    def test_public_files_endpoint(self):
        """Test public files endpoint."""
        self.client.force_authenticate(user=self.other_user)
        url = reverse("fileupload-public")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only include public files
        file_ids = [f["id"] for f in response.data["results"]]
        self.assertNotIn(str(self.private_file.id), file_ids)
        self.assertIn(str(self.public_file.id), file_ids)

    def test_signed_upload_url_endpoint(self):
        """Test signed upload URL endpoint."""
        self.client.force_authenticate(user=self.user)
        url = reverse("fileupload-signed-upload-url")

        data = {
            "filename": "test.pdf",
            "content_type": "application/pdf",
            "max_size": 1024 * 1024,  # 1MB
        }

        with patch.object(
            FileService,
            "get_upload_url",
            return_value={"url": "https://example.com/upload", "fields": {}},
        ):
            response = self.client.post(url, data)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("upload_url", response.data)
            self.assertIn("fields", response.data)
            self.assertIn("storage_path", response.data)

    def test_file_filtering_by_type(self):
        """Test file filtering by file type."""
        # Create an image file
        image_file = FileUpload.objects.create(
            original_filename="test.jpg",
            filename="test.jpg",
            file_type=FileType.IMAGE,
            mime_type="image/jpeg",
            file_size=1024,
            storage_path="uploads/test/test.jpg",
            is_public=True,
            created_by=self.user,
            updated_by=self.user,
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("fileupload-list")

        # Filter by image type
        response = self.client.get(url, {"file_type": FileType.IMAGE})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        file_ids = [f["id"] for f in response.data["results"]]
        self.assertIn(str(image_file.id), file_ids)
        self.assertNotIn(str(self.private_file.id), file_ids)  # Document file

    def test_file_filtering_by_public_status(self):
        """Test file filtering by public status."""
        self.client.force_authenticate(user=self.user)
        url = reverse("fileupload-list")

        # Filter by public files only
        response = self.client.get(url, {"is_public": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        file_ids = [f["id"] for f in response.data["results"]]
        self.assertIn(str(self.public_file.id), file_ids)
        self.assertNotIn(str(self.private_file.id), file_ids)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class FileManagementIntegrationTestCase(TestCase):
    """Integration tests for complete file management workflows."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", name="Test User"
        )

    @patch("apps.files.services.default_storage")
    def test_complete_file_upload_workflow(self, mock_storage):
        """Test complete file upload workflow."""
        # Mock storage operations
        mock_storage.save.return_value = "uploads/1/test_file.pdf"
        mock_storage.exists.return_value = True
        mock_storage.delete.return_value = True

        # 1. Create and upload file
        file_content = b"Test PDF content for workflow"
        test_file = SimpleUploadedFile(
            "workflow_test.pdf", file_content, content_type="application/pdf"
        )
        test_file.size = len(file_content)

        # 2. Upload file using service
        file_upload = FileService.upload_file(
            file=test_file,
            user=self.user,
            description="Workflow test file",
            tags="test,workflow",
            is_public=False,
        )

        # 3. Verify file was created correctly
        self.assertIsInstance(file_upload, FileUpload)
        self.assertEqual(file_upload.original_filename, "workflow_test.pdf")
        self.assertEqual(file_upload.file_type, FileType.DOCUMENT)
        self.assertEqual(file_upload.created_by, self.user)
        self.assertFalse(file_upload.is_public)

        # 4. Test access permissions
        self.assertTrue(file_upload.can_access(self.user))
        self.assertFalse(file_upload.can_access(None))

        # 5. Test download counter
        initial_count = file_upload.download_count
        file_upload.increment_download_count()
        file_upload.refresh_from_db()
        self.assertEqual(file_upload.download_count, initial_count + 1)

        # 6. Test file deletion
        file_id = file_upload.id
        result = FileService.delete_file(file_upload)
        self.assertTrue(result)
        self.assertFalse(FileUpload.objects.filter(id=file_id).exists())

    def test_file_expiration_workflow(self):
        """Test file expiration and cleanup workflow."""
        # Create files with different expiration times
        now = timezone.now()

        # Expired file
        expired_file = FileUpload.objects.create(
            original_filename="expired.pdf",
            filename="expired.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/expired.pdf",
            expires_at=now - timedelta(hours=2),
            is_public=True,
            created_by=self.user,
            updated_by=self.user,
        )

        # Soon to expire file
        soon_expired_file = FileUpload.objects.create(
            original_filename="soon_expired.pdf",
            filename="soon_expired.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/soon_expired.pdf",
            expires_at=now + timedelta(minutes=30),
            is_public=True,
            created_by=self.user,
            updated_by=self.user,
        )

        # Non-expiring file
        permanent_file = FileUpload.objects.create(
            original_filename="permanent.pdf",
            filename="permanent.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/test/permanent.pdf",
            expires_at=None,
            is_public=True,
            created_by=self.user,
            updated_by=self.user,
        )

        # Test expiration status
        self.assertTrue(expired_file.is_expired)
        self.assertFalse(soon_expired_file.is_expired)
        self.assertFalse(permanent_file.is_expired)

        # Test access for expired files
        other_user = User.objects.create_user(
            email="other@example.com", password="otherpass123", name="Other User"
        )

        # Owner can still access expired files
        self.assertTrue(expired_file.can_access(self.user))
        # Other users cannot access expired files even if public
        self.assertFalse(expired_file.can_access(other_user))
        # Anonymous users cannot access expired files
        self.assertFalse(expired_file.can_access(None))

        # Non-expired public files are accessible
        self.assertTrue(soon_expired_file.can_access(other_user))
        self.assertTrue(permanent_file.can_access(None))

    def test_file_type_detection_workflow(self):
        """Test file type detection for various file types."""
        test_cases = [
            ("image.jpg", "image/jpeg", FileType.IMAGE),
            ("document.pdf", "application/pdf", FileType.DOCUMENT),
            ("video.mp4", "video/mp4", FileType.VIDEO),
            ("audio.mp3", "audio/mpeg", FileType.AUDIO),
            ("archive.zip", "application/zip", FileType.ARCHIVE),
            ("unknown.xyz", "application/octet-stream", FileType.OTHER),
        ]

        for filename, mime_type, expected_type in test_cases:
            with self.subTest(filename=filename):
                # Test through validation
                file_content = b"Test file content"
                test_file = SimpleUploadedFile(
                    filename, file_content, content_type=mime_type
                )
                test_file.size = len(file_content)

                validation = FileService.validate_file(test_file)
                self.assertEqual(validation["file_type"], expected_type)
                self.assertEqual(validation["mime_type"], mime_type)

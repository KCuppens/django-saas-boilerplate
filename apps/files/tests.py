"""Comprehensive tests for files app"""

import hashlib
import uuid
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.core.enums import FileType

from .models import FileUpload
from .serializers import (
    FileStatsSerializer,
    FileUploadCreateSerializer,
    FileUploadSerializer,
    SignedUrlSerializer,
)
from .services import FileService
from .views import file_download_view

User = get_user_model()


class FileUploadModelTest(TestCase):
    """Test FileUpload model functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User"
        )

    def test_file_upload_creation(self):
        """Test FileUpload model creation"""
        file_upload = FileUpload.objects.create(
            original_filename="test.txt",
            filename="unique-filename.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            checksum="abc123",
            storage_path="uploads/test/unique-filename.txt",
            is_public=False,
            description="Test file",
            tags="test,file",
            created_by=self.user,
            updated_by=self.user,
        )

        self.assertEqual(file_upload.original_filename, "test.txt")
        self.assertEqual(file_upload.file_type, FileType.DOCUMENT)
        self.assertEqual(file_upload.file_size, 1024)
        self.assertEqual(file_upload.created_by, self.user)
        self.assertFalse(file_upload.is_public)

    def test_file_upload_str_representation(self):
        """Test FileUpload string representation"""
        file_upload = FileUpload(original_filename="test.txt")
        self.assertEqual(str(file_upload), "test.txt")

    def test_file_size_human_property(self):
        """Test human readable file size property"""
        file_upload = FileUpload(file_size=1024)
        self.assertEqual(file_upload.file_size_human, "1.0 KB")

        file_upload = FileUpload(file_size=1048576)
        self.assertEqual(file_upload.file_size_human, "1.0 MB")

        file_upload = FileUpload(file_size=0)
        self.assertEqual(file_upload.file_size_human, "0 B")

    def test_is_expired_property(self):
        """Test file expiration check"""
        # Test file without expiration
        file_upload = FileUpload()
        self.assertFalse(file_upload.is_expired)

        # Test expired file
        past_time = timezone.now() - timezone.timedelta(hours=1)
        file_upload = FileUpload(expires_at=past_time)
        self.assertTrue(file_upload.is_expired)

        # Test future expiration
        future_time = timezone.now() + timezone.timedelta(hours=1)
        file_upload = FileUpload(expires_at=future_time)
        self.assertFalse(file_upload.is_expired)

    def test_is_image_property(self):
        """Test image type check"""
        file_upload = FileUpload(file_type=FileType.IMAGE)
        self.assertTrue(file_upload.is_image)

        file_upload = FileUpload(file_type=FileType.DOCUMENT)
        self.assertFalse(file_upload.is_image)

    def test_is_document_property(self):
        """Test document type check"""
        file_upload = FileUpload(file_type=FileType.DOCUMENT)
        self.assertTrue(file_upload.is_document)

        file_upload = FileUpload(file_type=FileType.IMAGE)
        self.assertFalse(file_upload.is_document)

    def test_can_access_public_file(self):
        """Test access control for public files"""
        file_upload = FileUpload(is_public=True, expires_at=None)

        # Public files are accessible to all users
        self.assertTrue(file_upload.can_access(None))
        self.assertTrue(file_upload.can_access(self.user))

    def test_can_access_expired_public_file(self):
        """Test access control for expired public files"""
        past_time = timezone.now() - timezone.timedelta(hours=1)
        file_upload = FileUpload(is_public=True, expires_at=past_time)

        # Expired public files are not accessible
        self.assertFalse(file_upload.can_access(None))
        self.assertFalse(file_upload.can_access(self.user))

    def test_can_access_private_file_owner(self):
        """Test access control for private files by owner"""
        file_upload = FileUpload(
            is_public=False,
            created_by=self.user
        )

        # Owner can access their private files
        self.assertTrue(file_upload.can_access(self.user))

        # Anonymous users cannot access private files
        self.assertFalse(file_upload.can_access(None))

    def test_can_access_private_file_admin(self):
        """Test access control for private files by admin"""
        admin_user = User.objects.create_user(
            email="admin@example.com",
            password="adminpass123",
            name="Admin User",
            is_staff=True,
            is_superuser=True,
        )

        # Mock is_admin method
        with patch.object(admin_user, 'is_admin', return_value=True):
            file_upload = FileUpload(
                is_public=False,
                created_by=self.user
            )

            # Admins can access all files
            self.assertTrue(file_upload.can_access(admin_user))

    def test_increment_download_count(self):
        """Test download counter increment"""
        file_upload = FileUpload.objects.create(
            original_filename="test.txt",
            filename="unique-filename.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/test/unique-filename.txt",
            created_by=self.user,
            updated_by=self.user,
        )

        initial_count = file_upload.download_count
        file_upload.increment_download_count()

        file_upload.refresh_from_db()
        self.assertEqual(file_upload.download_count, initial_count + 1)

    def test_get_download_url(self):
        """Test download URL generation"""
        file_upload = FileUpload.objects.create(
            original_filename="test.txt",
            filename="unique-filename.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/test/unique-filename.txt",
            created_by=self.user,
            updated_by=self.user,
        )

        with patch('apps.files.services.FileService.get_download_url') as mock_service:
            mock_service.return_value = "http://example.com/download/test.txt"
            url = file_upload.get_download_url()

            mock_service.assert_called_once_with(file_upload, 3600)
            self.assertEqual(url, "http://example.com/download/test.txt")

    def test_get_upload_url(self):
        """Test upload URL generation"""
        file_upload = FileUpload(
            storage_path="uploads/test/unique-filename.txt"
        )

        with patch('apps.files.services.FileService.get_upload_url') as mock_service:
            mock_service.return_value = {"url": "http://example.com/upload"}
            result = file_upload.get_upload_url()

            mock_service.assert_called_once_with("uploads/test/unique-filename.txt", 3600)
            self.assertEqual(result, {"url": "http://example.com/upload"})


class FileServiceTest(TestCase):
    """Test FileService functionality"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User"
        )

    def test_file_type_mapping(self):
        """Test file type mapping"""
        self.assertEqual(FileService.FILE_TYPE_MAP["image/jpeg"], FileType.IMAGE)
        self.assertEqual(FileService.FILE_TYPE_MAP["application/pdf"], FileType.DOCUMENT)
        self.assertEqual(FileService.FILE_TYPE_MAP["video/mp4"], FileType.VIDEO)
        self.assertEqual(FileService.FILE_TYPE_MAP["audio/mpeg"], FileType.AUDIO)
        self.assertEqual(FileService.FILE_TYPE_MAP["application/zip"], FileType.ARCHIVE)

    @patch('apps.files.services.default_storage.save')
    def test_upload_file(self, mock_save):
        """Test file upload functionality"""
        mock_save.return_value = "uploads/1/test-file.txt"

        file_content = b"Test file content"
        uploaded_file = SimpleUploadedFile(
            "test.txt",
            file_content,
            content_type="text/plain"
        )

        # Mock file size
        uploaded_file.size = len(file_content)

        file_upload = FileService.upload_file(
            file=uploaded_file,
            user=self.user,
            description="Test upload",
            tags="test,upload",
            is_public=True
        )

        self.assertEqual(file_upload.original_filename, "test.txt")
        self.assertEqual(file_upload.file_type, FileType.DOCUMENT)
        self.assertEqual(file_upload.mime_type, "text/plain")
        self.assertEqual(file_upload.file_size, len(file_content))
        self.assertEqual(file_upload.created_by, self.user)
        self.assertTrue(file_upload.is_public)
        self.assertEqual(file_upload.description, "Test upload")
        self.assertEqual(file_upload.tags, "test,upload")

        # Check that checksum was calculated
        expected_checksum = hashlib.sha256(file_content).hexdigest()
        self.assertEqual(file_upload.checksum, expected_checksum)

    @patch('apps.files.services.default_storage')
    def test_get_download_url_public_file(self, mock_storage):
        """Test download URL generation for public files"""
        mock_storage.url.return_value = "http://example.com/media/test.txt"
        mock_storage.hasattr = lambda obj, attr: attr == "url"

        file_upload = FileUpload(
            id=uuid.uuid4(),
            is_public=True,
            storage_path="uploads/test.txt"
        )

        with patch('hasattr', return_value=True):
            url = FileService.get_download_url(file_upload)
            self.assertEqual(url, "http://example.com/media/test.txt")

    @patch('apps.files.services.default_storage')
    def test_get_download_url_private_file_with_presigned(self, mock_storage):
        """Test download URL generation for private files with presigned URLs"""
        mock_storage.generate_presigned_url.return_value = "http://example.com/presigned/test.txt"

        file_upload = FileUpload(
            id=uuid.uuid4(),
            is_public=False,
            storage_path="uploads/test.txt"
        )

        with patch('hasattr', return_value=True):
            url = FileService.get_download_url(file_upload, expires_in=7200)

            mock_storage.generate_presigned_url.assert_called_once_with(
                "uploads/test.txt",
                expires_in=7200,
                method="GET"
            )
            self.assertEqual(url, "http://example.com/presigned/test.txt")

    @patch('apps.files.services.default_storage')
    def test_get_download_url_fallback(self, mock_storage):
        """Test download URL fallback for local development"""
        file_upload = FileUpload(
            id=uuid.uuid4(),
            is_public=False,
            storage_path="uploads/test.txt"
        )

        with patch('hasattr', return_value=False):
            with patch('django.urls.reverse') as mock_reverse:
                mock_reverse.return_value = "/api/files/download/test-id/"

                url = FileService.get_download_url(file_upload)
                mock_reverse.assert_called_once_with(
                    "file_download",
                    kwargs={"file_id": file_upload.id}
                )
                self.assertEqual(url, "/api/files/download/test-id/")

    @patch('apps.files.services.default_storage')
    def test_get_upload_url_with_presigned_post(self, mock_storage):
        """Test upload URL generation with presigned POST"""
        mock_storage.generate_presigned_post.return_value = {
            "url": "http://example.com/upload",
            "fields": {"key": "value"}
        }

        with patch('hasattr', return_value=True):
            result = FileService.get_upload_url(
                storage_path="uploads/test.txt",
                expires_in=7200,
                content_type="text/plain",
                max_size=1024
            )

            mock_storage.generate_presigned_post.assert_called_once_with(
                "uploads/test.txt",
                expires_in=7200,
                conditions=[
                    ["eq", "$Content-Type", "text/plain"],
                    ["content-length-range", "0", "1024"]
                ]
            )
            self.assertEqual(result, {
                "url": "http://example.com/upload",
                "fields": {"key": "value"}
            })

    @patch('apps.files.services.default_storage')
    def test_delete_file_success(self, mock_storage):
        """Test successful file deletion"""
        mock_storage.exists.return_value = True
        mock_storage.delete.return_value = None

        file_upload = FileUpload.objects.create(
            original_filename="test.txt",
            filename="unique-filename.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/test/unique-filename.txt",
            created_by=self.user,
            updated_by=self.user,
        )

        result = FileService.delete_file(file_upload)

        self.assertTrue(result)
        mock_storage.exists.assert_called_once_with(file_upload.storage_path)
        mock_storage.delete.assert_called_once_with(file_upload.storage_path)

        # Check that database record was deleted
        self.assertFalse(FileUpload.objects.filter(id=file_upload.id).exists())

    @patch('apps.files.services.default_storage')
    def test_delete_file_error(self, mock_storage):
        """Test file deletion with error"""
        mock_storage.exists.return_value = True
        mock_storage.delete.side_effect = Exception("Storage error")

        file_upload = FileUpload.objects.create(
            original_filename="test.txt",
            filename="unique-filename.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/test/unique-filename.txt",
            created_by=self.user,
            updated_by=self.user,
        )

        result = FileService.delete_file(file_upload)

        self.assertFalse(result)
        # Check that database record still exists
        self.assertTrue(FileUpload.objects.filter(id=file_upload.id).exists())

    def test_validate_file_valid(self):
        """Test file validation with valid file"""
        file_content = b"Test file content"
        uploaded_file = SimpleUploadedFile(
            "test.txt",
            file_content,
            content_type="text/plain"
        )
        uploaded_file.size = len(file_content)

        result = FileService.validate_file(uploaded_file)

        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["file_type"], FileType.DOCUMENT)
        self.assertEqual(result["mime_type"], "text/plain")

    def test_validate_file_too_large(self):
        """Test file validation with oversized file"""
        file_content = b"x" * (11 * 1024 * 1024)  # 11MB
        uploaded_file = SimpleUploadedFile(
            "large.txt",
            file_content,
            content_type="text/plain"
        )
        uploaded_file.size = len(file_content)

        result = FileService.validate_file(uploaded_file, max_size_mb=10)

        self.assertFalse(result["valid"])
        self.assertIn("File size", result["errors"][0])

    def test_validate_file_invalid_extension(self):
        """Test file validation with invalid extension"""
        file_content = b"Test file content"
        uploaded_file = SimpleUploadedFile(
            "test.xyz",
            file_content,
            content_type="application/octet-stream"
        )
        uploaded_file.size = len(file_content)

        result = FileService.validate_file(uploaded_file)

        self.assertFalse(result["valid"])
        self.assertIn("File extension '.xyz' not allowed", result["errors"][0])

    def test_validate_file_dangerous_extension(self):
        """Test file validation with dangerous extension"""
        file_content = b"malicious content"
        uploaded_file = SimpleUploadedFile(
            "malware.exe",
            file_content,
            content_type="application/octet-stream"
        )
        uploaded_file.size = len(file_content)

        result = FileService.validate_file(uploaded_file)

        self.assertFalse(result["valid"])
        self.assertIn("security reasons", result["errors"][0])

    def test_cleanup_expired_files(self):
        """Test cleanup of expired files"""
        # Create expired file
        past_time = timezone.now() - timezone.timedelta(hours=1)
        expired_file = FileUpload.objects.create(
            original_filename="expired.txt",
            filename="expired-file.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/expired-file.txt",
            expires_at=past_time,
            created_by=self.user,
            updated_by=self.user,
        )

        # Create non-expired file
        future_time = timezone.now() + timezone.timedelta(hours=1)
        FileUpload.objects.create(
            original_filename="active.txt",
            filename="active-file.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/active-file.txt",
            expires_at=future_time,
            created_by=self.user,
            updated_by=self.user,
        )

        with patch.object(FileService, 'delete_file') as mock_delete:
            mock_delete.return_value = True

            result = FileService.cleanup_expired_files()

            self.assertEqual(result["deleted"], 1)
            self.assertEqual(result["errors"], 0)
            mock_delete.assert_called_once_with(expired_file)


class FileUploadSerializerTest(TestCase):
    """Test FileUpload serializers"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User"
        )
        self.file_upload = FileUpload.objects.create(
            original_filename="test.txt",
            filename="unique-filename.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/test/unique-filename.txt",
            created_by=self.user,
            updated_by=self.user,
        )

    def test_file_upload_serializer(self):
        """Test FileUpload serialization"""
        serializer = FileUploadSerializer(self.file_upload)
        data = serializer.data

        self.assertEqual(data["original_filename"], "test.txt")
        self.assertEqual(data["file_type"], FileType.DOCUMENT)
        self.assertEqual(data["file_size"], 1024)
        self.assertEqual(data["file_size_human"], "1.0 KB")

    def test_file_upload_serializer_with_request_context(self):
        """Test FileUpload serialization with request context"""
        # Mock request
        mock_request = Mock()
        mock_request.user = self.user
        mock_request.build_absolute_uri.return_value = "http://example.com/download/"

        # Mock can_access to return True
        with patch.object(self.file_upload, 'can_access', return_value=True):
            serializer = FileUploadSerializer(
                self.file_upload,
                context={"request": mock_request}
            )
            data = serializer.data

            self.assertEqual(data["download_url"], "http://example.com/download/")

    def test_file_upload_create_serializer(self):
        """Test FileUploadCreateSerializer validation"""
        file_content = b"Test file content"
        uploaded_file = SimpleUploadedFile(
            "test.txt",
            file_content,
            content_type="text/plain"
        )

        data = {
            "file": uploaded_file,
            "description": "Test file",
            "tags": "test,upload",
            "is_public": True
        }

        serializer = FileUploadCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_signed_url_serializer_valid(self):
        """Test SignedUrlSerializer with valid data"""
        data = {
            "filename": "test.txt",
            "content_type": "text/plain",
            "max_size": 1024
        }

        serializer = SignedUrlSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_signed_url_serializer_invalid_filename(self):
        """Test SignedUrlSerializer with invalid filename"""
        data = {
            "filename": "test/../dangerous.txt",
            "content_type": "text/plain"
        }

        serializer = SignedUrlSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("filename", serializer.errors)

    def test_signed_url_serializer_no_extension(self):
        """Test SignedUrlSerializer with filename without extension"""
        data = {
            "filename": "test",
            "content_type": "text/plain"
        }

        serializer = SignedUrlSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("Filename must have an extension", str(serializer.errors))

    def test_file_stats_serializer(self):
        """Test FileStatsSerializer"""
        data = {
            "total_files": 10,
            "total_size": 1048576,
            "total_size_human": "1.0 MB",
            "file_types": {"image": 5, "document": 5},
            "recent_uploads": ["file1.txt", "file2.jpg"]
        }

        serializer = FileStatsSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class FileUploadViewSetTest(APITestCase):
    """Test FileUploadViewSet API endpoints"""

    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User"
        )
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="adminpass123",
            name="Admin User",
            is_staff=True,
            is_superuser=True,
        )
        self.client = APIClient()

    @patch('apps.featureflags.helpers.require_feature_flag')
    def test_list_files_authenticated(self, mock_feature_flag):
        """Test listing files for authenticated user"""
        mock_feature_flag.return_value = lambda func: func

        self.client.force_authenticate(user=self.user)

        # Create test files
        FileUpload.objects.create(
            original_filename="user_file.txt",
            filename="user-file.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/user-file.txt",
            created_by=self.user,
            updated_by=self.user,
        )

        FileUpload.objects.create(
            original_filename="public_file.txt",
            filename="public-file.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/public-file.txt",
            is_public=True,
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        url = reverse("file-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)  # User's file + public file

    @patch('apps.featureflags.helpers.require_feature_flag')
    def test_list_files_with_filters(self, mock_feature_flag):
        """Test listing files with filters"""
        mock_feature_flag.return_value = lambda func: func

        self.client.force_authenticate(user=self.user)

        # Create test files
        FileUpload.objects.create(
            original_filename="image.jpg",
            filename="image.jpg",
            file_type=FileType.IMAGE,
            mime_type="image/jpeg",
            file_size=1024,
            storage_path="uploads/image.jpg",
            created_by=self.user,
            updated_by=self.user,
        )

        FileUpload.objects.create(
            original_filename="document.pdf",
            filename="document.pdf",
            file_type=FileType.DOCUMENT,
            mime_type="application/pdf",
            file_size=1024,
            storage_path="uploads/document.pdf",
            created_by=self.user,
            updated_by=self.user,
        )

        # Test filter by file type
        url = reverse("file-list")
        response = self.client.get(url, {"file_type": FileType.IMAGE})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["file_type"], FileType.IMAGE)

    @patch('apps.featureflags.helpers.require_feature_flag')
    @patch('apps.files.services.FileService.upload_file')
    @patch('apps.files.services.FileService.validate_file')
    def test_upload_file_success(self, mock_validate, mock_upload, mock_feature_flag):
        """Test successful file upload"""
        mock_feature_flag.return_value = lambda func: func
        mock_validate.return_value = {"valid": True, "errors": []}
        mock_upload.return_value = FileUpload(
            id=uuid.uuid4(),
            original_filename="test.txt",
            filename="unique-filename.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/test/unique-filename.txt",
        )

        self.client.force_authenticate(user=self.user)

        file_content = b"Test file content"
        uploaded_file = SimpleUploadedFile(
            "test.txt",
            file_content,
            content_type="text/plain"
        )

        url = reverse("file-list")
        response = self.client.post(
            url,
            {
                "file": uploaded_file,
                "description": "Test upload",
                "is_public": True
            },
            format="multipart"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_validate.assert_called_once()
        mock_upload.assert_called_once()

    @patch('apps.featureflags.helpers.require_feature_flag')
    @patch('apps.files.services.FileService.validate_file')
    def test_upload_file_validation_error(self, mock_validate, mock_feature_flag):
        """Test file upload with validation error"""
        mock_feature_flag.return_value = lambda func: func
        mock_validate.return_value = {
            "valid": False,
            "errors": ["File too large"]
        }

        self.client.force_authenticate(user=self.user)

        file_content = b"x" * (11 * 1024 * 1024)  # 11MB
        uploaded_file = SimpleUploadedFile(
            "large.txt",
            file_content,
            content_type="text/plain"
        )

        url = reverse("file-list")
        response = self.client.post(
            url,
            {
                "file": uploaded_file,
                "description": "Test upload"
            },
            format="multipart"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("errors", response.data)

    @patch('apps.featureflags.helpers.require_feature_flag')
    def test_get_download_url(self, mock_feature_flag):
        """Test getting download URL for file"""
        mock_feature_flag.return_value = lambda func: func

        file_upload = FileUpload.objects.create(
            original_filename="test.txt",
            filename="unique-filename.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/test/unique-filename.txt",
            created_by=self.user,
            updated_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

        with patch.object(file_upload, 'get_download_url') as mock_get_url:
            mock_get_url.return_value = "http://example.com/download/test.txt"

            url = reverse("file-download-url", kwargs={"pk": file_upload.id})
            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["download_url"], "http://example.com/download/test.txt")
            self.assertEqual(response.data["filename"], "test.txt")

    @patch('apps.featureflags.helpers.require_feature_flag')
    @patch('django.core.files.storage.default_storage.exists')
    @patch('django.core.files.storage.default_storage.open')
    def test_download_file(self, mock_open, mock_exists, mock_feature_flag):
        """Test direct file download"""
        mock_feature_flag.return_value = lambda func: func
        mock_exists.return_value = True
        mock_file_obj = Mock()
        mock_open.return_value = mock_file_obj

        file_upload = FileUpload.objects.create(
            original_filename="test.txt",
            filename="unique-filename.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/test/unique-filename.txt",
            created_by=self.user,
            updated_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

        url = reverse("file-download", kwargs={"pk": file_upload.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check that download count was incremented
        file_upload.refresh_from_db()
        self.assertEqual(file_upload.download_count, 1)

    @patch('apps.featureflags.helpers.require_feature_flag')
    @patch('apps.files.services.FileService.get_upload_url')
    def test_signed_upload_url(self, mock_get_upload_url, mock_feature_flag):
        """Test getting signed upload URL"""
        mock_feature_flag.return_value = lambda func: func
        mock_get_upload_url.return_value = {
            "url": "http://example.com/upload",
            "fields": {"key": "value"}
        }

        self.client.force_authenticate(user=self.user)

        url = reverse("file-signed-upload-url")
        data = {
            "filename": "test.txt",
            "content_type": "text/plain",
            "max_size": 1024
        }

        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["upload_url"], "http://example.com/upload")
        self.assertEqual(response.data["fields"], {"key": "value"})

    @patch('apps.featureflags.helpers.require_feature_flag')
    def test_my_files(self, mock_feature_flag):
        """Test getting current user's files"""
        mock_feature_flag.return_value = lambda func: func

        # Create files for different users
        FileUpload.objects.create(
            original_filename="my_file.txt",
            filename="my-file.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/my-file.txt",
            created_by=self.user,
            updated_by=self.user,
        )

        FileUpload.objects.create(
            original_filename="other_file.txt",
            filename="other-file.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/other-file.txt",
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        self.client.force_authenticate(user=self.user)

        url = reverse("file-my-files")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["original_filename"], "my_file.txt")

    @patch('apps.featureflags.helpers.require_feature_flag')
    def test_public_files(self, mock_feature_flag):
        """Test getting public files"""
        mock_feature_flag.return_value = lambda func: func

        # Create public and private files
        FileUpload.objects.create(
            original_filename="public_file.txt",
            filename="public-file.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/public-file.txt",
            is_public=True,
            created_by=self.user,
            updated_by=self.user,
        )

        FileUpload.objects.create(
            original_filename="private_file.txt",
            filename="private-file.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/private-file.txt",
            is_public=False,
            created_by=self.user,
            updated_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

        url = reverse("file-public")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["original_filename"], "public_file.txt")

    @patch('apps.featureflags.helpers.require_feature_flag')
    def test_delete_file(self, mock_feature_flag):
        """Test file deletion"""
        mock_feature_flag.return_value = lambda func: func

        file_upload = FileUpload.objects.create(
            original_filename="test.txt",
            filename="unique-filename.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/test/unique-filename.txt",
            created_by=self.user,
            updated_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

        url = reverse("file-detail", kwargs={"pk": file_upload.id})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_unauthenticated_access(self):
        """Test unauthenticated access is denied"""
        url = reverse("file-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.django_db
class TestFileUploadURLs:
    """Test file upload URL patterns"""

    def test_file_download_view(self, user, sample_file):
        """Test standalone file download view"""
        file_upload = FileUpload.objects.create(
            original_filename="test.txt",
            filename="unique-filename.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=len(sample_file.read()),
            storage_path="uploads/test/unique-filename.txt",
            is_public=True,
            created_by=user,
            updated_by=user,
        )

        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get(f'/files/download/{file_upload.id}/')
        request.user = user

        with patch('django.core.files.storage.default_storage.exists') as mock_exists:
            with patch('django.core.files.storage.default_storage.open') as mock_open:
                mock_exists.return_value = True
                mock_open.return_value = Mock()

                response = file_download_view(request, file_upload.id)

                assert response.status_code == 200

        # Check download count was incremented
        file_upload.refresh_from_db()
        assert file_upload.download_count == 1

    def test_file_download_view_not_found(self, user):
        """Test file download view with non-existent file"""
        from django.http import Http404
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get('/files/download/nonexistent/')
        request.user = user

        with pytest.raises(Http404):
            file_download_view(request, uuid.uuid4())

    def test_file_download_view_no_access(self, user, admin_user):
        """Test file download view with no access permission"""
        file_upload = FileUpload.objects.create(
            original_filename="private.txt",
            filename="private-file.txt",
            file_type=FileType.DOCUMENT,
            mime_type="text/plain",
            file_size=1024,
            storage_path="uploads/private-file.txt",
            is_public=False,
            created_by=admin_user,
            updated_by=admin_user,
        )

        from django.http import Http404
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get(f'/files/download/{file_upload.id}/')
        request.user = user

        with pytest.raises(Http404):
            file_download_view(request, file_upload.id)

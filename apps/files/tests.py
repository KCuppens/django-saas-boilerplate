import hashlib
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from apps.core.enums import FileType
from .models import FileUpload
from .services import FileService

User = get_user_model()


class FileUploadModelTestCase(TestCase):
    """Test FileUpload model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="test@example.com",
            name="Test User",
            password="testpass123"
        )
        self.admin_user = User.objects.create_superuser(
            email="admin@example.com",
            name="Admin User",
            password="adminpass123"
        )
        
        self.file_upload = FileUpload.objects.create(
            original_filename="test.jpg",
            filename="test_unique.jpg",
            file_type=FileType.IMAGE,
            mime_type="image/jpeg",
            file_size=1024,
            storage_path="uploads/test_unique.jpg",
            created_by=self.user,
            updated_by=self.user,
        )

    def test_file_upload_str_representation(self):
        """Test FileUpload string representation"""
        self.assertEqual(str(self.file_upload), "test.jpg")

    def test_file_size_human_property(self):
        """Test file_size_human property"""
        self.file_upload.file_size = 1024
        self.assertEqual(self.file_upload.file_size_human, "1.0 KB")
        
        self.file_upload.file_size = 1048576
        self.assertEqual(self.file_upload.file_size_human, "1.0 MB")

    def test_is_expired_property_not_expired(self):
        """Test is_expired property when not expired"""
        future_date = timezone.now() + timedelta(hours=1)
        self.file_upload.expires_at = future_date
        self.assertFalse(self.file_upload.is_expired)

    def test_is_expired_property_expired(self):
        """Test is_expired property when expired"""
        past_date = timezone.now() - timedelta(hours=1)
        self.file_upload.expires_at = past_date
        self.assertTrue(self.file_upload.is_expired)

    def test_is_expired_property_no_expiry(self):
        """Test is_expired property when no expiry set"""
        self.file_upload.expires_at = None
        self.assertFalse(self.file_upload.is_expired)

    def test_is_image_property(self):
        """Test is_image property"""
        self.file_upload.file_type = FileType.IMAGE
        self.assertTrue(self.file_upload.is_image)
        
        self.file_upload.file_type = FileType.DOCUMENT
        self.assertFalse(self.file_upload.is_image)

    def test_is_document_property(self):
        """Test is_document property"""
        self.file_upload.file_type = FileType.DOCUMENT
        self.assertTrue(self.file_upload.is_document)
        
        self.file_upload.file_type = FileType.IMAGE
        self.assertFalse(self.file_upload.is_document)

    def test_can_access_public_file(self):
        """Test can_access for public files"""
        self.file_upload.is_public = True
        self.file_upload.expires_at = None
        
        # Anonymous user
        self.assertTrue(self.file_upload.can_access(None))
        
        # Any authenticated user
        other_user = User.objects.create_user(
            email="other@example.com",
            name="Other User",
            password="otherpass123"
        )
        self.assertTrue(self.file_upload.can_access(other_user))

    def test_can_access_private_file_owner(self):
        """Test can_access for private file by owner"""
        self.file_upload.is_public = False
        self.assertTrue(self.file_upload.can_access(self.user))

    def test_can_access_private_file_admin(self):
        """Test can_access for private file by admin"""
        self.file_upload.is_public = False
        
        # Mock the is_admin method
        self.admin_user.is_admin = Mock(return_value=True)
        self.assertTrue(self.file_upload.can_access(self.admin_user))

    def test_can_access_private_file_denied(self):
        """Test can_access denied for private file"""
        self.file_upload.is_public = False
        
        other_user = User.objects.create_user(
            email="other@example.com",
            name="Other User",
            password="otherpass123"
        )
        other_user.is_admin = Mock(return_value=False)
        self.assertFalse(self.file_upload.can_access(other_user))

    def test_can_access_expired_public_file(self):
        """Test can_access denied for expired public file"""
        self.file_upload.is_public = True
        self.file_upload.expires_at = timezone.now() - timedelta(hours=1)
        
        self.assertFalse(self.file_upload.can_access(None))

    def test_increment_download_count(self):
        """Test increment_download_count method"""
        initial_count = self.file_upload.download_count
        self.file_upload.increment_download_count()
        
        self.file_upload.refresh_from_db()
        self.assertEqual(self.file_upload.download_count, initial_count + 1)

    @patch('apps.files.services.FileService.get_download_url')
    def test_get_download_url(self, mock_get_url):
        """Test get_download_url method"""
        mock_get_url.return_value = "https://example.com/download/test"
        
        url = self.file_upload.get_download_url()
        
        self.assertEqual(url, "https://example.com/download/test")
        mock_get_url.assert_called_once_with(self.file_upload, 3600)

    @patch('apps.files.services.FileService.get_upload_url')
    def test_get_upload_url(self, mock_get_url):
        """Test get_upload_url method"""
        mock_get_url.return_value = {"url": "https://example.com/upload", "fields": {}}
        
        url_data = self.file_upload.get_upload_url()
        
        self.assertEqual(url_data["url"], "https://example.com/upload")
        mock_get_url.assert_called_once_with(self.file_upload.storage_path, 3600)


class FileServiceTestCase(TestCase):
    """Test FileService class"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="test@example.com",
            name="Test User",
            password="testpass123"
        )

    def create_test_file(self, filename="test.txt", content=b"test content", mime_type="text/plain"):
        """Helper to create test uploaded file"""
        return SimpleUploadedFile(
            filename,
            content,
            content_type=mime_type
        )

    def test_file_type_mapping(self):
        """Test FILE_TYPE_MAP contains expected mappings"""
        self.assertEqual(FileService.FILE_TYPE_MAP["image/jpeg"], FileType.IMAGE)
        self.assertEqual(FileService.FILE_TYPE_MAP["application/pdf"], FileType.DOCUMENT)
        self.assertEqual(FileService.FILE_TYPE_MAP["video/mp4"], FileType.VIDEO)
        self.assertEqual(FileService.FILE_TYPE_MAP["audio/mpeg"], FileType.AUDIO)
        self.assertEqual(FileService.FILE_TYPE_MAP["application/zip"], FileType.ARCHIVE)

    @patch('apps.files.services.default_storage')
    def test_upload_file_success(self, mock_storage):
        """Test successful file upload"""
        mock_storage.save.return_value = "uploads/123/test_unique.txt"
        
        test_file = self.create_test_file()
        
        file_upload = FileService.upload_file(
            file=test_file,
            user=self.user,
            description="Test file",
            tags="test,upload",
            is_public=True
        )
        
        self.assertEqual(file_upload.original_filename, "test.txt")
        self.assertEqual(file_upload.mime_type, "text/plain")
        self.assertEqual(file_upload.file_type, FileType.DOCUMENT)
        self.assertEqual(file_upload.created_by, self.user)
        self.assertEqual(file_upload.description, "Test file")
        self.assertEqual(file_upload.tags, "test,upload")
        self.assertTrue(file_upload.is_public)

    @patch('apps.files.services.default_storage')
    def test_upload_file_checksum_calculation(self, mock_storage):
        """Test file checksum calculation during upload"""
        mock_storage.save.return_value = "uploads/123/test_unique.txt"
        
        content = b"test content for checksum"
        test_file = self.create_test_file(content=content)
        
        file_upload = FileService.upload_file(file=test_file, user=self.user)
        
        expected_checksum = hashlib.sha256(content).hexdigest()
        self.assertEqual(file_upload.checksum, expected_checksum)

    @patch('apps.files.services.default_storage')
    def test_get_download_url_public_file(self, mock_storage):
        """Test get_download_url for public file"""
        mock_storage.url.return_value = "https://example.com/test.jpg"
        mock_storage.url_exists = True
        
        file_upload = FileUpload(
            storage_path="uploads/test.jpg",
            is_public=True
        )
        
        # Mock hasattr to return True for url method
        with patch('builtins.hasattr', return_value=True):
            url = FileService.get_download_url(file_upload)
            self.assertEqual(url, "https://example.com/test.jpg")

    @patch('apps.files.services.default_storage')
    def test_get_download_url_presigned(self, mock_storage):
        """Test get_download_url with presigned URL"""
        mock_storage.generate_presigned_url.return_value = "https://example.com/presigned/test.jpg"
        
        file_upload = FileUpload(
            id=uuid.uuid4(),
            storage_path="uploads/test.jpg",
            is_public=False
        )
        
        # Mock hasattr to return True for generate_presigned_url method
        with patch('builtins.hasattr', return_value=True):
            url = FileService.get_download_url(file_upload, expires_in=1800)
            self.assertEqual(url, "https://example.com/presigned/test.jpg")
            mock_storage.generate_presigned_url.assert_called_once_with(
                "uploads/test.jpg",
                expires_in=1800,
                method="GET"
            )

    @patch('apps.files.services.default_storage')
    @patch('django.urls.reverse')
    def test_get_download_url_fallback(self, mock_reverse, mock_storage):
        """Test get_download_url fallback to local serving"""
        mock_reverse.return_value = "/files/download/123/"
        
        file_upload = FileUpload(
            id="123",
            storage_path="uploads/test.jpg",
            is_public=False
        )
        
        # Mock hasattr to return False (no S3 methods available)
        with patch('builtins.hasattr', return_value=False):
            url = FileService.get_download_url(file_upload)
            self.assertEqual(url, "/files/download/123/")

    @patch('apps.files.services.default_storage')
    def test_get_upload_url_presigned_post(self, mock_storage):
        """Test get_upload_url with presigned POST"""
        mock_storage.generate_presigned_post.return_value = {
            "url": "https://example.com/upload",
            "fields": {"key": "uploads/test.jpg"}
        }
        
        with patch('builtins.hasattr', return_value=True):
            result = FileService.get_upload_url(
                "uploads/test.jpg",
                expires_in=1800,
                content_type="image/jpeg",
                max_size=5242880
            )
            
            self.assertEqual(result["url"], "https://example.com/upload")
            self.assertEqual(result["fields"]["key"], "uploads/test.jpg")

    @patch('apps.files.services.default_storage')
    def test_delete_file_success(self, mock_storage):
        """Test successful file deletion"""
        mock_storage.exists.return_value = True
        mock_storage.delete.return_value = None
        
        file_upload = FileUpload.objects.create(
            original_filename="test.jpg",
            filename="test_unique.jpg",
            file_type=FileType.IMAGE,
            mime_type="image/jpeg",
            file_size=1024,
            storage_path="uploads/test_unique.jpg",
            created_by=self.user,
            updated_by=self.user,
        )
        
        result = FileService.delete_file(file_upload)
        
        self.assertTrue(result)
        mock_storage.exists.assert_called_once_with("uploads/test_unique.jpg")
        mock_storage.delete.assert_called_once_with("uploads/test_unique.jpg")
        
        # Verify file was deleted from database
        self.assertFalse(FileUpload.objects.filter(id=file_upload.id).exists())

    @patch('apps.files.services.default_storage')
    def test_delete_file_storage_error(self, mock_storage):
        """Test file deletion with storage error"""
        mock_storage.exists.side_effect = Exception("Storage error")
        
        file_upload = FileUpload.objects.create(
            original_filename="test.jpg",
            filename="test_unique.jpg",
            file_type=FileType.IMAGE,
            mime_type="image/jpeg",
            file_size=1024,
            storage_path="uploads/test_unique.jpg",
            created_by=self.user,
            updated_by=self.user,
        )
        
        result = FileService.delete_file(file_upload)
        
        self.assertFalse(result)
        # File should still exist in database
        self.assertTrue(FileUpload.objects.filter(id=file_upload.id).exists())

    def test_validate_file_success(self):
        """Test successful file validation"""
        test_file = self.create_test_file("test.pdf", b"test content", "application/pdf")
        
        result = FileService.validate_file(test_file, max_size_mb=10)
        
        self.assertTrue(result["valid"])
        self.assertEqual(result["file_type"], FileType.DOCUMENT)
        self.assertEqual(result["mime_type"], "application/pdf")
        self.assertEqual(result["errors"], [])

    def test_validate_file_size_exceeded(self):
        """Test file validation with size exceeded"""
        # Create a large file content
        large_content = b"x" * (2 * 1024 * 1024)  # 2MB content
        test_file = self.create_test_file("large.pdf", large_content, "application/pdf")
        
        result = FileService.validate_file(test_file, max_size_mb=1)  # 1MB limit
        
        self.assertFalse(result["valid"])
        self.assertIn("File size", result["errors"][0])
        self.assertIn("exceeds maximum", result["errors"][0])

    def test_validate_file_invalid_extension(self):
        """Test file validation with invalid extension"""
        test_file = self.create_test_file("test.xyz", b"test content", "application/octet-stream")
        
        result = FileService.validate_file(test_file)
        
        self.assertFalse(result["valid"])
        self.assertIn("File extension '.xyz' not allowed", result["errors"])

    def test_validate_file_dangerous_extension(self):
        """Test file validation with dangerous extension"""
        test_file = self.create_test_file("malware.exe", b"test content", "application/octet-stream")
        
        result = FileService.validate_file(test_file)
        
        self.assertFalse(result["valid"])
        self.assertIn("not allowed", result["errors"][0])

    def test_validate_file_unsupported_mime_type(self):
        """Test file validation with unsupported MIME type"""
        test_file = self.create_test_file("test.txt", b"test content", "application/unknown")
        
        result = FileService.validate_file(test_file)
        
        # Should have warnings but still be valid if extension is allowed
        self.assertIn("may not be supported", result["warnings"][0])

    @patch('apps.files.services.FileService.delete_file')
    def test_cleanup_expired_files(self, mock_delete):
        """Test cleanup of expired files"""
        # Create expired files
        expired_file1 = FileUpload.objects.create(
            original_filename="expired1.jpg",
            filename="expired1_unique.jpg",
            file_type=FileType.IMAGE,
            mime_type="image/jpeg",
            file_size=1024,
            storage_path="uploads/expired1_unique.jpg",
            expires_at=timezone.now() - timedelta(hours=1),
            created_by=self.user,
            updated_by=self.user,
        )
        
        expired_file2 = FileUpload.objects.create(
            original_filename="expired2.jpg",
            filename="expired2_unique.jpg",
            file_type=FileType.IMAGE,
            mime_type="image/jpeg",
            file_size=1024,
            storage_path="uploads/expired2_unique.jpg",
            expires_at=timezone.now() - timedelta(hours=2),
            created_by=self.user,
            updated_by=self.user,
        )
        
        # Create non-expired file
        FileUpload.objects.create(
            original_filename="valid.jpg",
            filename="valid_unique.jpg",
            file_type=FileType.IMAGE,
            mime_type="image/jpeg",
            file_size=1024,
            storage_path="uploads/valid_unique.jpg",
            expires_at=timezone.now() + timedelta(hours=1),
            created_by=self.user,
            updated_by=self.user,
        )
        
        # Mock successful deletion
        mock_delete.return_value = True
        
        result = FileService.cleanup_expired_files()
        
        self.assertEqual(result["deleted"], 2)
        self.assertEqual(result["errors"], 0)
        self.assertEqual(mock_delete.call_count, 2)

    @patch('apps.files.services.FileService.delete_file')
    def test_cleanup_expired_files_with_errors(self, mock_delete):
        """Test cleanup of expired files with deletion errors"""
        # Create expired file
        FileUpload.objects.create(
            original_filename="expired.jpg",
            filename="expired_unique.jpg",
            file_type=FileType.IMAGE,
            mime_type="image/jpeg",
            file_size=1024,
            storage_path="uploads/expired_unique.jpg",
            expires_at=timezone.now() - timedelta(hours=1),
            created_by=self.user,
            updated_by=self.user,
        )
        
        # Mock failed deletion
        mock_delete.return_value = False
        
        result = FileService.cleanup_expired_files()
        
        self.assertEqual(result["deleted"], 0)
        self.assertEqual(result["errors"], 1)
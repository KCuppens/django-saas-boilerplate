from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.utils import timezone

from rest_framework.test import APIClient, APITestCase

from apps.core.enums import FileType
from apps.files.models import FileUpload
from apps.files.serializers import (
    FileStatsSerializer,
    FileUploadCreateSerializer,
    FileUploadSerializer,
    SignedUrlSerializer,
)

User = get_user_model()


class FileUploadSerializerTestCase(TestCase):
    """Test FileUploadSerializer"""

    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )

        self.file_upload = FileUpload.objects.create(
            original_filename="test.jpg",
            filename="test_unique.jpg",
            file_type=FileType.IMAGE,
            mime_type="image/jpeg",
            file_size=1024,
            storage_path="uploads/test_unique.jpg",
            is_public=True,
            created_by=self.user,
            updated_by=self.user,
        )

    def test_serializer_fields(self):
        """Test serializer includes all expected fields"""
        request = self.factory.get("/")
        request.user = self.user

        serializer = FileUploadSerializer(
            self.file_upload, context={"request": request}
        )

        expected_fields = [
            "id",
            "original_filename",
            "filename",
            "file_type",
            "mime_type",
            "file_size",
            "file_size_human",
            "checksum",
            "is_public",
            "description",
            "tags",
            "expires_at",
            "is_expired",
            "download_count",
            "created_at",
            "updated_at",
            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
            "download_url",
        ]

        for field in expected_fields:
            self.assertIn(field, serializer.data)

    def test_created_by_name_field(self):
        """Test created_by_name field"""
        request = self.factory.get("/")
        request.user = self.user

        serializer = FileUploadSerializer(
            self.file_upload, context={"request": request}
        )

        self.assertEqual(serializer.data["created_by_name"], self.user.get_full_name())

    def test_file_size_human_field(self):
        """Test file_size_human field"""
        request = self.factory.get("/")
        request.user = self.user

        serializer = FileUploadSerializer(
            self.file_upload, context={"request": request}
        )

        self.assertEqual(serializer.data["file_size_human"], "1.0 KB")

    def test_is_expired_field(self):
        """Test is_expired field"""
        request = self.factory.get("/")
        request.user = self.user

        # Test non-expired file
        serializer = FileUploadSerializer(
            self.file_upload, context={"request": request}
        )
        self.assertFalse(serializer.data["is_expired"])

        # Test expired file
        self.file_upload.expires_at = timezone.now() - timedelta(hours=1)
        self.file_upload.save()

        serializer = FileUploadSerializer(
            self.file_upload, context={"request": request}
        )
        self.assertTrue(serializer.data["is_expired"])

    def test_get_download_url_with_access(self):
        """Test get_download_url when user has access"""
        request = self.factory.get("/")
        request.user = self.user

        with patch.object(self.file_upload, "can_access", return_value=True):
            serializer = FileUploadSerializer(
                self.file_upload, context={"request": request}
            )

            self.assertIsNotNone(serializer.data["download_url"])
            self.assertIn(str(self.file_upload.id), serializer.data["download_url"])

    def test_get_download_url_without_access(self):
        """Test get_download_url when user has no access"""
        request = self.factory.get("/")
        request.user = self.user

        with patch.object(self.file_upload, "can_access", return_value=False):
            serializer = FileUploadSerializer(
                self.file_upload, context={"request": request}
            )

            self.assertIsNone(serializer.data["download_url"])

    def test_get_download_url_no_request(self):
        """Test get_download_url with no request in context"""
        serializer = FileUploadSerializer(self.file_upload)

        self.assertIsNone(serializer.data["download_url"])

    def test_read_only_fields(self):
        """Test that read-only fields cannot be updated"""
        request = self.factory.get("/")
        request.user = self.user

        data = {
            "id": "new-id",
            "filename": "hacked.jpg",
            "file_size": 999999,
            "download_count": 100,
            "description": "Updated description",  # This should be allowed
        }

        serializer = FileUploadSerializer(
            self.file_upload, data=data, partial=True, context={"request": request}
        )

        self.assertTrue(serializer.is_valid())
        updated_file = serializer.save()

        # Read-only fields should not change
        self.assertEqual(updated_file.filename, "test_unique.jpg")
        self.assertEqual(updated_file.file_size, 1024)
        self.assertEqual(updated_file.download_count, 0)

        # Writable field should change
        self.assertEqual(updated_file.description, "Updated description")


class FileUploadCreateSerializerTestCase(TestCase):
    """Test FileUploadCreateSerializer"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )

    def test_serializer_fields(self):
        """Test serializer has expected fields"""
        serializer = FileUploadCreateSerializer()

        expected_fields = ["file", "description", "tags", "is_public", "expires_at"]

        for field in expected_fields:
            self.assertIn(field, serializer.fields)

    def test_file_field_write_only(self):
        """Test file field is write-only"""
        serializer = FileUploadCreateSerializer()

        self.assertTrue(serializer.fields["file"].write_only)

    def test_valid_data(self):
        """Test serializer with valid data"""
        file_content = b"test file content"
        test_file = SimpleUploadedFile(
            "test.txt", file_content, content_type="text/plain"
        )

        data = {
            "file": test_file,
            "description": "Test file",
            "tags": "test,upload",
            "is_public": True,
        }

        serializer = FileUploadCreateSerializer(data=data)

        self.assertTrue(serializer.is_valid())

    def test_invalid_data(self):
        """Test serializer with invalid data"""
        data = {"description": "Test file without file field"}

        serializer = FileUploadCreateSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("file", serializer.errors)


class SignedUrlSerializerTestCase(TestCase):
    """Test SignedUrlSerializer"""

    def test_valid_filename(self):
        """Test serializer with valid filename"""
        data = {
            "filename": "test_file.pdf",
            "content_type": "application/pdf",
            "max_size": 5242880,
        }

        serializer = SignedUrlSerializer(data=data)

        self.assertTrue(serializer.is_valid())

    def test_filename_without_extension(self):
        """Test filename without extension"""
        data = {"filename": "test_file_no_extension"}

        serializer = SignedUrlSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("filename", serializer.errors)

    def test_dangerous_filename_characters(self):
        """Test filename with dangerous characters"""
        dangerous_filenames = [
            "file../test.pdf",
            "file/test.pdf",
            "file\\test.pdf",
            "file<test.pdf",
            "file>test.pdf",
            "file:test.pdf",
            'file"test.pdf',
            "file|test.pdf",
            "file?test.pdf",
            "file*test.pdf",
        ]

        for filename in dangerous_filenames:
            with self.subTest(filename=filename):
                data = {"filename": filename}
                serializer = SignedUrlSerializer(data=data)

                self.assertFalse(serializer.is_valid())
                self.assertIn("filename", serializer.errors)

    def test_max_size_validation(self):
        """Test max_size field validation"""
        # Test valid size
        data = {"filename": "test.pdf", "max_size": 1024}
        serializer = SignedUrlSerializer(data=data)
        self.assertTrue(serializer.is_valid())

        # Test size too small
        data["max_size"] = 0
        serializer = SignedUrlSerializer(data=data)
        self.assertFalse(serializer.is_valid())

        # Test size too large
        data["max_size"] = 200 * 1024 * 1024  # 200MB
        serializer = SignedUrlSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_optional_fields(self):
        """Test optional fields"""
        data = {"filename": "test.pdf"}

        serializer = SignedUrlSerializer(data=data)

        self.assertTrue(serializer.is_valid())
        self.assertNotIn("content_type", serializer.validated_data)
        self.assertNotIn("max_size", serializer.validated_data)


class FileStatsSerializerTestCase(TestCase):
    """Test FileStatsSerializer"""

    def test_serializer_fields(self):
        """Test serializer has expected fields"""
        data = {
            "total_files": 10,
            "total_size": 1048576,
            "total_size_human": "1.0 MB",
            "file_types": {"image": 5, "document": 5},
            "recent_uploads": ["file1.jpg", "file2.pdf"],
        }

        serializer = FileStatsSerializer(data=data)

        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["total_files"], 10)
        self.assertEqual(serializer.validated_data["total_size"], 1048576)
        self.assertEqual(serializer.validated_data["total_size_human"], "1.0 MB")


class FileViewsTestCase(APITestCase):
    """Test file views (simplified since full views aren't provided)"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com", name="Test User", password="testpass123"
        )

        self.file_upload = FileUpload.objects.create(
            original_filename="test.jpg",
            filename="test_unique.jpg",
            file_type=FileType.IMAGE,
            mime_type="image/jpeg",
            file_size=1024,
            storage_path="uploads/test_unique.jpg",
            is_public=True,
            created_by=self.user,
            updated_by=self.user,
        )

    def test_file_serializer_integration(self):
        """Test file serializer with actual model data"""
        self.client.force_authenticate(user=self.user)

        serializer = FileUploadSerializer(
            self.file_upload, context={"request": self.client.request()}
        )

        data = serializer.data

        # Test all expected fields are present
        self.assertEqual(data["original_filename"], "test.jpg")
        self.assertEqual(data["file_type"], FileType.IMAGE)
        self.assertEqual(data["mime_type"], "image/jpeg")
        self.assertEqual(data["file_size"], 1024)
        self.assertEqual(data["file_size_human"], "1.0 KB")
        self.assertTrue(data["is_public"])
        self.assertFalse(data["is_expired"])

    @patch("apps.files.services.FileService.upload_file")
    def test_file_upload_serializer_integration(self, mock_upload):
        """Test file upload serializer integration"""
        mock_upload.return_value = self.file_upload

        file_content = b"test file content"
        test_file = SimpleUploadedFile(
            "upload_test.txt", file_content, content_type="text/plain"
        )

        data = {
            "file": test_file,
            "description": "Integration test file",
            "tags": "test,integration",
            "is_public": False,
        }

        serializer = FileUploadCreateSerializer(data=data)

        self.assertTrue(serializer.is_valid())

        # Test that we could call save with proper context
        # (In a real view, this would create the file upload)
        validated_data = serializer.validated_data
        self.assertEqual(validated_data["description"], "Integration test file")
        self.assertEqual(validated_data["tags"], "test,integration")
        self.assertFalse(validated_data["is_public"])
        self.assertEqual(validated_data["file"].name, "upload_test.txt")

    def test_signed_url_serializer_integration(self):
        """Test signed URL serializer with various inputs"""
        test_cases = [
            {
                "data": {"filename": "document.pdf", "content_type": "application/pdf"},
                "should_be_valid": True,
            },
            {
                "data": {"filename": "image.jpg", "max_size": 1024000},
                "should_be_valid": True,
            },
            {"data": {"filename": "no_extension"}, "should_be_valid": False},
            {"data": {"filename": "../malicious.exe"}, "should_be_valid": False},
        ]

        for case in test_cases:
            with self.subTest(data=case["data"]):
                serializer = SignedUrlSerializer(data=case["data"])

                if case["should_be_valid"]:
                    self.assertTrue(
                        serializer.is_valid(),
                        f"Expected valid data: {case['data']}, errors: {serializer.errors}",
                    )
                else:
                    self.assertFalse(
                        serializer.is_valid(), f"Expected invalid data: {case['data']}"
                    )

    def test_file_stats_serializer_integration(self):
        """Test file stats serializer with realistic data"""
        # Simulate stats data that might come from a view
        stats_data = {
            "total_files": 25,
            "total_size": 52428800,  # 50MB
            "total_size_human": "50.0 MB",
            "file_types": {"image": 15, "document": 8, "video": 2},
            "recent_uploads": [
                {
                    "filename": "recent1.jpg",
                    "uploaded_at": timezone.now().isoformat(),
                    "size": 1024,
                },
                {
                    "filename": "recent2.pdf",
                    "uploaded_at": timezone.now().isoformat(),
                    "size": 2048,
                },
            ],
        }

        serializer = FileStatsSerializer(data=stats_data)

        self.assertTrue(serializer.is_valid())
        validated = serializer.validated_data

        self.assertEqual(validated["total_files"], 25)
        self.assertEqual(validated["total_size"], 52428800)
        self.assertEqual(validated["file_types"]["image"], 15)
        self.assertEqual(len(validated["recent_uploads"]), 2)

    def test_serializer_performance_with_multiple_files(self):
        """Test serializer performance with multiple files"""
        # Create multiple file uploads
        files = []
        for i in range(10):
            file_upload = FileUpload.objects.create(
                original_filename=f"test{i}.jpg",
                filename=f"test{i}_unique.jpg",
                file_type=FileType.IMAGE,
                mime_type="image/jpeg",
                file_size=1024 * (i + 1),
                storage_path=f"uploads/test{i}_unique.jpg",
                is_public=True,
                created_by=self.user,
                updated_by=self.user,
            )
            files.append(file_upload)

        # Test serializing multiple files
        request = RequestFactory().get("/")
        request.user = self.user

        serializer = FileUploadSerializer(
            files, many=True, context={"request": request}
        )

        data = serializer.data

        self.assertEqual(len(data), 10)
        for i, file_data in enumerate(data):
            self.assertEqual(file_data["original_filename"], f"test{i}.jpg")
            self.assertEqual(file_data["file_size"], 1024 * (i + 1))

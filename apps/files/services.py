"""File handling services for the Django SaaS boilerplate."""

import hashlib
import logging
import os
import uuid
from typing import Any, Optional

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.urls import reverse

from apps.core.enums import FileType

from .models import FileUpload

logger = logging.getLogger(__name__)


class FileService:
    """Service for handling file operations."""

    # File type mappings
    FILE_TYPE_MAP = {
        "image/jpeg": FileType.IMAGE,
        "image/png": FileType.IMAGE,
        "image/gif": FileType.IMAGE,
        "image/webp": FileType.IMAGE,
        "image/svg+xml": FileType.IMAGE,
        "application/pdf": FileType.DOCUMENT,
        "application/msword": FileType.DOCUMENT,
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ): FileType.DOCUMENT,
        "text/plain": FileType.DOCUMENT,
        "text/csv": FileType.DOCUMENT,
        "video/mp4": FileType.VIDEO,
        "video/webm": FileType.VIDEO,
        "video/quicktime": FileType.VIDEO,
        "audio/mpeg": FileType.AUDIO,
        "audio/wav": FileType.AUDIO,
        "audio/ogg": FileType.AUDIO,
        "application/zip": FileType.ARCHIVE,
        "application/x-tar": FileType.ARCHIVE,
        "application/gzip": FileType.ARCHIVE,
    }

    @classmethod
    def upload_file(
        cls,
        file,
        user,
        description: str = "",
        tags: str = "",
        is_public: bool = False,
        expires_at=None,
    ) -> FileUpload:
        """Upload a file and create a FileUpload record."""
        # Generate unique filename
        file_extension = os.path.splitext(file.name)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        storage_path = f"uploads/{user.id}/{unique_filename}"

        # Calculate file checksum
        file.seek(0)
        file_content = file.read()
        checksum = hashlib.sha256(file_content).hexdigest()
        file.seek(0)  # Reset file pointer

        # Determine file type
        mime_type = getattr(file, "content_type", "application/octet-stream")
        file_type = cls.FILE_TYPE_MAP.get(mime_type, FileType.OTHER)

        # Store file
        stored_path = default_storage.save(storage_path, ContentFile(file_content))

        # Create FileUpload record
        file_upload = FileUpload.objects.create(
            original_filename=file.name,
            filename=unique_filename,
            file_type=file_type,
            mime_type=mime_type,
            file_size=file.size,
            checksum=checksum,
            storage_path=stored_path,
            is_public=is_public,
            description=description,
            tags=tags,
            expires_at=expires_at,
            created_by=user,
            updated_by=user,
        )

        logger.info(
            "File uploaded: %s -> %s by user %s", file.name, stored_path, user.id
        )

        return file_upload

    @classmethod
    def get_download_url(cls, file_upload: FileUpload, expires_in: int = 3600) -> str:
        """Get signed download URL for file."""
        # For public files, return direct URL
        if file_upload.is_public and hasattr(default_storage, "url"):
            try:
                return default_storage.url(file_upload.storage_path)
            except Exception as e:
                logger.warning(
                    "Failed to generate direct URL for file %s: %s", file_upload.id, e
                )

        # For private files or S3, generate signed URL
        if hasattr(default_storage, "generate_presigned_url"):
            try:
                return default_storage.generate_presigned_url(
                    file_upload.storage_path,
                    expires_in=expires_in,
                    method="GET",
                )
            except Exception as e:
                logger.error("Failed to generate presigned URL: %s", str(e))

        # Fallback to local file serving (development)
        return reverse("file_download", kwargs={"file_id": file_upload.id})

    @classmethod
    def get_upload_url(
        cls,
        storage_path: str,
        expires_in: int = 3600,
        content_type: Optional[str] = None,
        max_size: Optional[int] = None,
    ) -> dict[str, Any]:
        """Get signed upload URL and required fields."""
        if hasattr(default_storage, "generate_presigned_post"):
            try:
                conditions = []
                if content_type:
                    conditions.append(["eq", "$Content-Type", content_type])
                if max_size:
                    conditions.append(["content-length-range", "0", str(max_size)])

                return default_storage.generate_presigned_post(
                    storage_path, expires_in=expires_in, conditions=conditions
                )
            except Exception as e:
                logger.error("Failed to generate presigned upload URL: %s", str(e))

        # Fallback for local development
        return {"url": reverse("file_upload"), "fields": {}}

    @classmethod
    def delete_file(cls, file_upload: FileUpload) -> bool:
        """Delete file from storage and database."""
        try:
            # Delete from storage
            if default_storage.exists(file_upload.storage_path):
                default_storage.delete(file_upload.storage_path)

            # Delete database record
            file_upload.delete()

            logger.info("File deleted: %s", file_upload.storage_path)
            return True

        except Exception as e:
            logger.error(
                "Failed to delete file %s: %s", file_upload.storage_path, str(e)
            )
            return False

    @classmethod
    def validate_file(cls, file, max_size_mb: int = 10) -> dict[str, Any]:
        """Validate uploaded file."""
        errors = []
        warnings = []

        # Check file size
        max_size_bytes = max_size_mb * 1024 * 1024
        if file.size > max_size_bytes:
            errors.append(
                f"File size ({file.size} bytes) exceeds maximum allowed "
                f"({max_size_bytes} bytes)"
            )

        # Check file extension
        allowed_extensions = getattr(
            settings,
            "ALLOWED_FILE_EXTENSIONS",
            [
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".pdf",
                ".doc",
                ".docx",
                ".txt",
                ".csv",
            ],
        )

        file_extension = os.path.splitext(file.name)[1].lower()
        if file_extension not in allowed_extensions:
            errors.append(f"File extension '{file_extension}' not allowed")

        # Check MIME type
        mime_type = getattr(file, "content_type", "application/octet-stream")
        allowed_mime_types = getattr(
            settings, "ALLOWED_MIME_TYPES", list(cls.FILE_TYPE_MAP.keys())
        )

        if mime_type not in allowed_mime_types:
            warnings.append(f"MIME type '{mime_type}' may not be supported")

        # Check for potential security issues
        dangerous_extensions = [
            ".exe",
            ".bat",
            ".cmd",
            ".com",
            ".pif",
            ".scr",
            ".vbs",
            ".js",
        ]
        if file_extension in dangerous_extensions:
            errors.append(
                f"File type '{file_extension}' is not allowed for security reasons"
            )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "file_type": cls.FILE_TYPE_MAP.get(mime_type, FileType.OTHER),
            "mime_type": mime_type,
        }

    @classmethod
    def cleanup_expired_files(cls) -> dict[str, int]:
        """Clean up expired files."""
        from django.utils import timezone

        expired_files = FileUpload.objects.filter(expires_at__lt=timezone.now())

        deleted_count = 0
        error_count = 0

        for file_upload in expired_files:
            if cls.delete_file(file_upload):
                deleted_count += 1
            else:
                error_count += 1

        return {"deleted": deleted_count, "errors": error_count}

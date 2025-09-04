from django.contrib import admin

from .models import FileUpload


@admin.register(FileUpload)
class FileUploadAdmin(admin.ModelAdmin):
    """Admin interface for FileUpload"""

    list_display = [
        "original_filename",
        "file_type",
        "file_size_human",
        "is_public",
        "download_count",
        "created_by",
        "created_at",
    ]
    list_filter = ["file_type", "is_public", "created_at", "expires_at"]
    search_fields = ["original_filename", "description", "tags"]
    ordering = ["-created_at"]
    readonly_fields = [
        "id",
        "filename",
        "file_type",
        "mime_type",
        "file_size",
        "file_size_human",
        "checksum",
        "storage_path",
        "download_count",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (None, {"fields": ("original_filename", "filename", "file_type", "mime_type")}),
        (
            "File Details",
            {"fields": ("file_size", "file_size_human", "checksum", "storage_path")},
        ),
        ("Settings", {"fields": ("is_public", "description", "tags", "expires_at")}),
        ("Statistics", {"fields": ("download_count",), "classes": ("collapse",)}),
        (
            "Metadata",
            {
                "fields": ("created_by", "updated_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def file_size_human(self, obj):
        """Display human-readable file size"""
        return obj.file_size_human

    file_size_human.short_description = "File Size"

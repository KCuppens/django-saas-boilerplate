from django.contrib import admin

from .models import Note


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    """Admin interface for Note model"""

    list_display = ["title", "is_public", "created_by", "created_at", "updated_at"]
    list_filter = ["is_public", "created_at", "updated_at"]
    search_fields = ["title", "content", "tags"]
    ordering = ["-created_at"]
    readonly_fields = ["created_by", "updated_by", "created_at", "updated_at"]

    fieldsets = (
        (None, {"fields": ("title", "content", "is_public", "tags")}),
        (
            "Metadata",
            {
                "fields": ("created_by", "updated_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """Set user tracking fields"""
        if not change:  # Creating new object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

"""Comprehensive tests for API models"""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.api.models import Note

User = get_user_model()


@pytest.mark.django_db
class TestNoteModel:
    """Comprehensive tests for Note model"""

    @pytest.fixture
    def user(self):
        """Create a test user"""
        return User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User",
        )

    @pytest.fixture
    def another_user(self):
        """Create another test user"""
        return User.objects.create_user(
            email="another@example.com",
            password="anotherpass123",
            name="Another User",
        )

    def test_create_note_minimal(self, user):
        """Test creating a note with minimal required fields"""
        note = Note.objects.create(
            title="Test Note",
            content="Test content",
            created_by=user,
            updated_by=user,
        )

        assert note.title == "Test Note"
        assert note.content == "Test content"
        assert note.is_public is False  # Default value
        assert note.tags == ""  # Default empty
        assert note.created_by == user
        assert note.updated_by == user
        assert note.created_at is not None
        assert note.updated_at is not None

    def test_create_note_full(self, user):
        """Test creating a note with all fields"""
        note = Note.objects.create(
            title="Full Test Note",
            content="Full test content with more details",
            is_public=True,
            tags="test, full, comprehensive",
            created_by=user,
            updated_by=user,
        )

        assert note.title == "Full Test Note"
        assert note.content == "Full test content with more details"
        assert note.is_public is True
        assert note.tags == "test, full, comprehensive"
        assert note.created_by == user
        assert note.updated_by == user

    def test_note_string_representation(self, user):
        """Test note __str__ method"""
        note = Note.objects.create(
            title="String Repr Test",
            content="Content",
            created_by=user,
            updated_by=user,
        )

        assert str(note) == "String Repr Test"

    def test_note_string_representation_empty_title(self, user):
        """Test note __str__ method with empty title"""
        note = Note.objects.create(
            title="",
            content="Content without title",
            created_by=user,
            updated_by=user,
        )

        assert str(note) == ""

    def test_note_verbose_names(self):
        """Test model verbose names"""
        assert Note._meta.verbose_name == "Note"
        assert Note._meta.verbose_name_plural == "Notes"

    def test_note_ordering(self, user):
        """Test note default ordering"""
        # Create notes with different timestamps
        note1 = Note.objects.create(
            title="First Note",
            content="First content",
            created_by=user,
            updated_by=user,
        )

        note2 = Note.objects.create(
            title="Second Note",
            content="Second content",
            created_by=user,
            updated_by=user,
        )

        notes = list(Note.objects.all())
        # Should be ordered by -created_at, so note2 should come first
        assert notes[0] == note2
        assert notes[1] == note1

    def test_note_indexes(self):
        """Test that indexes are created correctly"""
        indexes = Note._meta.indexes
        assert len(indexes) == 2

        # Check field names in indexes
        index_fields = [index.fields for index in indexes]
        assert ["created_by", "created_at"] in index_fields
        assert ["is_public", "created_at"] in index_fields

    def test_tag_list_property_empty_tags(self, user):
        """Test tag_list property with empty tags"""
        note = Note.objects.create(
            title="Empty Tags Note",
            content="Content",
            tags="",
            created_by=user,
            updated_by=user,
        )

        assert note.tag_list == []

    def test_tag_list_property_single_tag(self, user):
        """Test tag_list property with single tag"""
        note = Note.objects.create(
            title="Single Tag Note",
            content="Content",
            tags="single",
            created_by=user,
            updated_by=user,
        )

        assert note.tag_list == ["single"]

    def test_tag_list_property_multiple_tags(self, user):
        """Test tag_list property with multiple tags"""
        note = Note.objects.create(
            title="Multiple Tags Note",
            content="Content",
            tags="tag1, tag2, tag3",
            created_by=user,
            updated_by=user,
        )

        assert note.tag_list == ["tag1", "tag2", "tag3"]

    def test_tag_list_property_with_whitespace(self, user):
        """Test tag_list property handles whitespace correctly"""
        note = Note.objects.create(
            title="Whitespace Tags Note",
            content="Content",
            tags="  tag1  ,  tag2  ,  tag3  ",
            created_by=user,
            updated_by=user,
        )

        assert note.tag_list == ["tag1", "tag2", "tag3"]

    def test_tag_list_property_with_empty_segments(self, user):
        """Test tag_list property filters empty segments"""
        note = Note.objects.create(
            title="Empty Segments Note",
            content="Content",
            tags="tag1, , tag2, ,tag3",
            created_by=user,
            updated_by=user,
        )

        assert note.tag_list == ["tag1", "tag2", "tag3"]

    def test_tag_list_property_no_tags_field(self, user):
        """Test tag_list property when tags field is None"""
        note = Note.objects.create(
            title="No Tags Note",
            content="Content",
            created_by=user,
            updated_by=user,
        )
        # Ensure tags is empty string by default
        note.tags = None
        note.save()

        # Even with None, should handle gracefully
        # This tests the robustness of the property
        try:
            tag_list = note.tag_list
            # If no exception, tags should be treated as empty
            assert tag_list == []
        except AttributeError:
            # This is acceptable behavior for None tags
            pass

    def test_tag_list_setter_with_list(self, user):
        """Test tag_list setter with list input"""
        note = Note.objects.create(
            title="Setter Test Note",
            content="Content",
            created_by=user,
            updated_by=user,
        )

        note.tag_list = ["python", "django", "test"]

        assert note.tags == "python, django, test"
        assert note.tag_list == ["python", "django", "test"]

    def test_tag_list_setter_with_empty_list(self, user):
        """Test tag_list setter with empty list"""
        note = Note.objects.create(
            title="Empty List Setter Note",
            content="Content",
            tags="existing, tags",
            created_by=user,
            updated_by=user,
        )

        note.tag_list = []

        assert note.tags == ""
        assert note.tag_list == []

    def test_tag_list_setter_with_string(self, user):
        """Test tag_list setter with string input"""
        note = Note.objects.create(
            title="String Setter Note",
            content="Content",
            created_by=user,
            updated_by=user,
        )

        note.tag_list = "manual string"

        assert note.tags == "manual string"

    def test_tag_list_setter_with_number(self, user):
        """Test tag_list setter with number input"""
        note = Note.objects.create(
            title="Number Setter Note",
            content="Content",
            created_by=user,
            updated_by=user,
        )

        note.tag_list = 12345

        assert note.tags == "12345"

    def test_note_field_max_lengths(self, user):
        """Test field max lengths"""
        # Test title max length (200 characters)
        long_title = "x" * 200
        note = Note.objects.create(
            title=long_title,
            content="Content",
            created_by=user,
            updated_by=user,
        )
        assert len(note.title) == 200

        # Test tags max length (500 characters)
        long_tags = "x" * 500
        note.tags = long_tags
        note.save()
        assert len(note.tags) == 500

    def test_note_field_validations(self, user):
        """Test field validations"""
        # Title is required
        with pytest.raises((IntegrityError, ValidationError)):
            note = Note(
                content="Content without title",
                created_by=user,
                updated_by=user,
            )
            note.full_clean()  # Triggers validation

        # Content is required
        with pytest.raises((IntegrityError, ValidationError)):
            note = Note(
                title="Title without content",
                created_by=user,
                updated_by=user,
            )
            note.full_clean()

    def test_note_boolean_field_default(self, user):
        """Test boolean field default values"""
        note = Note.objects.create(
            title="Boolean Test",
            content="Content",
            created_by=user,
            updated_by=user,
        )

        # is_public should default to False
        assert note.is_public is False

    def test_note_relationships(self, user, another_user):
        """Test foreign key relationships"""
        note = Note.objects.create(
            title="Relationship Test",
            content="Content",
            created_by=user,
            updated_by=another_user,
        )

        # Test forward relationships
        assert note.created_by == user
        assert note.updated_by == another_user

        # Test reverse relationships through related manager
        assert note in user.api_note_created.all()
        assert note in another_user.api_note_updated.all()

    def test_note_user_tracking_mixin_fields(self, user):
        """Test that UserTrackingMixin fields work correctly"""
        note = Note.objects.create(
            title="User Tracking Test",
            content="Content",
            created_by=user,
            updated_by=user,
        )

        # Test that fields exist and are set
        assert hasattr(note, 'created_by')
        assert hasattr(note, 'updated_by')
        assert note.created_by == user
        assert note.updated_by == user

        # Test that fields can be null
        note.created_by = None
        note.updated_by = None
        note.save()

        note.refresh_from_db()
        assert note.created_by is None
        assert note.updated_by is None

    def test_note_timestamp_mixin_fields(self, user):
        """Test that TimestampMixin fields work correctly"""
        note = Note.objects.create(
            title="Timestamp Test",
            content="Content",
            created_by=user,
            updated_by=user,
        )

        # Test that timestamp fields exist and are set
        assert hasattr(note, 'created_at')
        assert hasattr(note, 'updated_at')
        assert note.created_at is not None
        assert note.updated_at is not None

        # Test that updated_at changes on save
        original_updated_at = note.updated_at
        note.title = "Updated Title"
        note.save()

        note.refresh_from_db()
        assert note.updated_at > original_updated_at

    def test_note_help_text(self):
        """Test field help text"""
        tags_field = Note._meta.get_field('tags')
        assert tags_field.help_text == "Comma-separated tags"

    def test_note_verbose_field_names(self):
        """Test field verbose names"""
        title_field = Note._meta.get_field('title')
        content_field = Note._meta.get_field('content')
        is_public_field = Note._meta.get_field('is_public')
        tags_field = Note._meta.get_field('tags')

        assert title_field.verbose_name == "Title"
        assert content_field.verbose_name == "Content"
        assert is_public_field.verbose_name == "Public"
        assert tags_field.verbose_name == "Tags"

    def test_note_field_blank_options(self):
        """Test which fields allow blank values"""
        tags_field = Note._meta.get_field('tags')
        title_field = Note._meta.get_field('title')
        content_field = Note._meta.get_field('content')

        # Tags should allow blank
        assert tags_field.blank is True

        # Title and content should not allow blank by default
        assert title_field.blank is False
        assert content_field.blank is False

    def test_note_queryset_methods(self, user):
        """Test that basic queryset methods work"""
        # Create some notes
        note1 = Note.objects.create(
            title="First Note",
            content="First content",
            is_public=True,
            created_by=user,
            updated_by=user,
        )

        note2 = Note.objects.create(
            title="Second Note",
            content="Second content",
            is_public=False,
            created_by=user,
            updated_by=user,
        )

        # Test filtering
        public_notes = Note.objects.filter(is_public=True)
        assert note1 in public_notes
        assert note2 not in public_notes

        # Test counting
        assert Note.objects.count() == 2
        assert Note.objects.filter(is_public=True).count() == 1

        # Test ordering
        notes_by_title = Note.objects.order_by('title')
        assert list(notes_by_title) == [note1, note2]  # First, Second

    def test_note_update_fields(self, user):
        """Test updating specific fields"""
        note = Note.objects.create(
            title="Update Test",
            content="Original content",
            is_public=False,
            tags="original",
            created_by=user,
            updated_by=user,
        )

        original_updated_at = note.updated_at

        # Update only specific fields
        note.title = "Updated Title"
        note.is_public = True
        note.save(update_fields=['title', 'is_public', 'updated_at'])

        note.refresh_from_db()
        assert note.title == "Updated Title"
        assert note.is_public is True
        assert note.content == "Original content"  # Unchanged
        assert note.tags == "original"  # Unchanged
        assert note.updated_at > original_updated_at

    def test_note_bulk_operations(self, user):
        """Test bulk operations on notes"""
        # Create multiple notes
        notes_data = [
            Note(title=f"Bulk Note {i}", content=f"Content {i}",
                 created_by=user, updated_by=user)
            for i in range(5)
        ]

        notes = Note.objects.bulk_create(notes_data)
        assert len(notes) == 5
        assert Note.objects.count() == 5

        # Bulk update
        Note.objects.filter(title__startswith="Bulk").update(is_public=True)

        public_count = Note.objects.filter(is_public=True).count()
        assert public_count == 5

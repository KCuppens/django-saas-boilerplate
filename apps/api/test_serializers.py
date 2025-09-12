"""Comprehensive tests for API serializers"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.api.models import Note
from apps.api.serializers import (
    HealthCheckSerializer,
    NoteCreateUpdateSerializer,
    NoteSerializer,
)

User = get_user_model()


@pytest.mark.django_db
class TestNoteSerializer:
    """Test NoteSerializer functionality"""

    def test_serializer_fields(self):
        """Test that serializer includes all required fields"""
        serializer = NoteSerializer()
        expected_fields = {
            "id",
            "title",
            "content",
            "is_public",
            "tags",
            "tag_list",
            "created_at",
            "updated_at",
            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
        }
        assert set(serializer.fields.keys()) == expected_fields

    def test_read_only_fields(self):
        """Test that appropriate fields are read-only"""
        serializer = NoteSerializer()
        expected_read_only = {
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "created_by_name",
            "updated_by",
            "updated_by_name",
        }

        actual_read_only = set()
        for field_name, field in serializer.fields.items():
            if field.read_only:
                actual_read_only.add(field_name)

        assert actual_read_only == expected_read_only

    def test_serialize_note(self, user):
        """Test serializing a note instance"""
        note = Note.objects.create(
            title="Test Note",
            content="Test content",
            is_public=True,
            tags="tag1, tag2, tag3",
            created_by=user,
            updated_by=user,
        )

        serializer = NoteSerializer(note)
        data = serializer.data

        assert data["title"] == "Test Note"
        assert data["content"] == "Test content"
        assert data["is_public"] is True
        assert data["tags"] == "tag1, tag2, tag3"
        assert data["tag_list"] == ["tag1", "tag2", "tag3"]
        assert data["created_by"] == user.id
        assert data["created_by_name"] == user.get_full_name()
        assert data["updated_by"] == user.id
        assert data["updated_by_name"] == user.get_full_name()
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_serialize_note_without_tags(self, user):
        """Test serializing a note without tags"""
        note = Note.objects.create(
            title="Test Note",
            content="Test content",
            created_by=user,
            updated_by=user,
        )

        serializer = NoteSerializer(note)
        data = serializer.data

        assert data["tags"] == ""
        assert data["tag_list"] == []

    def test_serialize_note_with_empty_tags(self, user):
        """Test serializing a note with empty tags"""
        note = Note.objects.create(
            title="Test Note",
            content="Test content",
            tags="",
            created_by=user,
            updated_by=user,
        )

        serializer = NoteSerializer(note)
        data = serializer.data

        assert data["tags"] == ""
        assert data["tag_list"] == []

    def test_serialize_note_with_whitespace_tags(self, user):
        """Test serializing a note with tags containing whitespace"""
        note = Note.objects.create(
            title="Test Note",
            content="Test content",
            tags="  tag1  ,  tag2  ,  tag3  ",
            created_by=user,
            updated_by=user,
        )

        serializer = NoteSerializer(note)
        data = serializer.data

        assert data["tag_list"] == ["tag1", "tag2", "tag3"]

    def test_to_internal_value_with_tag_list(self):
        """Test converting tag_list to tags field"""
        serializer = NoteSerializer()
        data = {
            "title": "Test Note",
            "content": "Test content",
            "is_public": False,
            "tag_list": ["tag1", "tag2", "tag3"]
        }

        internal_data = serializer.to_internal_value(data)

        assert internal_data["tags"] == "tag1, tag2, tag3"
        assert "tag_list" not in internal_data

    def test_to_internal_value_without_tag_list(self):
        """Test internal value conversion without tag_list"""
        serializer = NoteSerializer()
        data = {
            "title": "Test Note",
            "content": "Test content",
            "is_public": False,
            "tags": "manual, tags"
        }

        internal_data = serializer.to_internal_value(data)

        assert internal_data["tags"] == "manual, tags"

    def test_to_internal_value_with_non_list_tag_list(self):
        """Test internal value conversion with non-list tag_list"""
        serializer = NoteSerializer()
        data = {
            "title": "Test Note",
            "content": "Test content",
            "is_public": False,
            "tag_list": "not_a_list"
        }

        internal_data = serializer.to_internal_value(data)

        # Should not modify data if tag_list is not a list
        assert internal_data.get("tags") != "not_a_list"

    def test_validation_required_fields(self):
        """Test validation of required fields"""
        serializer = NoteSerializer(data={})

        assert not serializer.is_valid()
        assert "title" in serializer.errors
        assert "content" in serializer.errors

    def test_validation_title_max_length(self):
        """Test title max length validation"""
        long_title = "x" * 201  # Exceeds max_length of 200
        serializer = NoteSerializer(data={
            "title": long_title,
            "content": "Test content"
        })

        assert not serializer.is_valid()
        assert "title" in serializer.errors

    def test_validation_valid_data(self):
        """Test validation with valid data"""
        serializer = NoteSerializer(data={
            "title": "Valid Title",
            "content": "Valid content",
            "is_public": True
        })

        assert serializer.is_valid()

    def test_tag_list_field_validation(self):
        """Test tag_list field validation"""
        serializer = NoteSerializer()
        tag_list_field = serializer.fields["tag_list"]

        # Valid tag list
        valid_tags = ["tag1", "tag2", "tag3"]
        tag_list_field.to_internal_value(valid_tags)

        # Invalid tag (too long)
        with pytest.raises(serializers.ValidationError):
            invalid_tags = ["x" * 51]  # Exceeds child max_length of 50
            tag_list_field.to_internal_value(invalid_tags)


@pytest.mark.django_db
class TestNoteCreateUpdateSerializer:
    """Test NoteCreateUpdateSerializer functionality"""

    def test_serializer_fields(self):
        """Test that serializer includes only create/update fields"""
        serializer = NoteCreateUpdateSerializer()
        expected_fields = {"title", "content", "is_public", "tag_list"}
        assert set(serializer.fields.keys()) == expected_fields

    def test_inherits_from_note_serializer(self):
        """Test that serializer inherits from NoteSerializer"""
        assert issubclass(NoteCreateUpdateSerializer, NoteSerializer)

    def test_serialize_for_create(self):
        """Test serializing data for create operation"""
        data = {
            "title": "New Note",
            "content": "New content",
            "is_public": False,
            "tag_list": ["new", "create"]
        }

        serializer = NoteCreateUpdateSerializer(data=data)
        assert serializer.is_valid()

        validated_data = serializer.validated_data
        assert validated_data["title"] == "New Note"
        assert validated_data["content"] == "New content"
        assert validated_data["is_public"] is False
        assert validated_data["tags"] == "new, create"

    def test_serialize_for_update(self, user):
        """Test serializing data for update operation"""
        note = Note.objects.create(
            title="Original Title",
            content="Original content",
            created_by=user,
            updated_by=user,
        )

        update_data = {
            "title": "Updated Title",
            "content": "Updated content",
            "is_public": True,
            "tag_list": ["updated"]
        }

        serializer = NoteCreateUpdateSerializer(note, data=update_data)
        assert serializer.is_valid()

        validated_data = serializer.validated_data
        assert validated_data["title"] == "Updated Title"
        assert validated_data["content"] == "Updated content"
        assert validated_data["is_public"] is True
        assert validated_data["tags"] == "updated"

    def test_partial_update(self, user):
        """Test partial update with only some fields"""
        note = Note.objects.create(
            title="Original Title",
            content="Original content",
            is_public=False,
            tags="original, tags",
            created_by=user,
            updated_by=user,
        )

        partial_data = {"title": "Partially Updated Title"}

        serializer = NoteCreateUpdateSerializer(note, data=partial_data, partial=True)
        assert serializer.is_valid()

        validated_data = serializer.validated_data
        assert validated_data["title"] == "Partially Updated Title"
        # Other fields should not be in validated_data for partial update
        assert "content" not in validated_data
        assert "is_public" not in validated_data
        assert "tags" not in validated_data

    def test_validation_empty_tag_list(self):
        """Test validation with empty tag_list"""
        data = {
            "title": "Test Title",
            "content": "Test content",
            "tag_list": []
        }

        serializer = NoteCreateUpdateSerializer(data=data)
        assert serializer.is_valid()

        validated_data = serializer.validated_data
        assert validated_data["tags"] == ""

    def test_validation_missing_tag_list(self):
        """Test validation without tag_list field"""
        data = {
            "title": "Test Title",
            "content": "Test content",
            "is_public": True
        }

        serializer = NoteCreateUpdateSerializer(data=data)
        assert serializer.is_valid()

        # tags field should not be set if tag_list not provided
        validated_data = serializer.validated_data
        assert "tags" not in validated_data


class TestHealthCheckSerializer:
    """Test HealthCheckSerializer functionality"""

    def test_serializer_fields(self):
        """Test that serializer includes all health check fields"""
        serializer = HealthCheckSerializer()
        expected_fields = {
            "status",
            "timestamp",
            "version",
            "database",
            "cache",
            "celery",
            "uptime",
            "memory_usage",
            "cpu_usage",
            "services",
            "errors",
        }
        assert set(serializer.fields.keys()) == expected_fields

    def test_required_fields(self):
        """Test required vs optional fields"""
        serializer = HealthCheckSerializer()

        required_fields = {"status", "timestamp", "database", "cache"}
        optional_fields = {
            "version", "celery", "uptime", "memory_usage",
            "cpu_usage", "services", "errors"
        }

        for field_name, field in serializer.fields.items():
            if field_name in required_fields:
                assert field.required or field.default != serializers.empty
            elif field_name in optional_fields:
                assert not field.required

    def test_serialize_minimal_health_data(self):
        """Test serializing minimal health check data"""
        from django.utils import timezone

        data = {
            "status": "healthy",
            "timestamp": timezone.now(),
            "database": True,
            "cache": True,
        }

        serializer = HealthCheckSerializer(data)
        serialized_data = serializer.data

        assert serialized_data["status"] == "healthy"
        assert serialized_data["database"] is True
        assert serialized_data["cache"] is True
        assert "timestamp" in serialized_data

    def test_serialize_full_health_data(self):
        """Test serializing complete health check data"""
        from django.utils import timezone

        data = {
            "status": "healthy",
            "timestamp": timezone.now(),
            "version": "1.0.0",
            "database": True,
            "cache": True,
            "celery": True,
            "uptime": "2.5 hours",
            "memory_usage": 45.2,
            "cpu_usage": 23.8,
            "services": {"redis": True, "postgres": True},
            "errors": [],
        }

        serializer = HealthCheckSerializer(data)
        serialized_data = serializer.data

        assert serialized_data["status"] == "healthy"
        assert serialized_data["version"] == "1.0.0"
        assert serialized_data["database"] is True
        assert serialized_data["cache"] is True
        assert serialized_data["celery"] is True
        assert serialized_data["uptime"] == "2.5 hours"
        assert serialized_data["memory_usage"] == 45.2
        assert serialized_data["cpu_usage"] == 23.8
        assert serialized_data["services"] == {"redis": True, "postgres": True}
        assert serialized_data["errors"] == []

    def test_serialize_unhealthy_status(self):
        """Test serializing unhealthy status with errors"""
        from django.utils import timezone

        data = {
            "status": "unhealthy",
            "timestamp": timezone.now(),
            "database": False,
            "cache": True,
            "errors": ["Database connection failed"],
        }

        serializer = HealthCheckSerializer(data)
        serialized_data = serializer.data

        assert serialized_data["status"] == "unhealthy"
        assert serialized_data["database"] is False
        assert serialized_data["cache"] is True
        assert serialized_data["errors"] == ["Database connection failed"]

    def test_field_types(self):
        """Test field types are correct"""
        serializer = HealthCheckSerializer()

        assert isinstance(serializer.fields["status"], serializers.CharField)
        assert isinstance(serializer.fields["timestamp"], serializers.DateTimeField)
        assert isinstance(serializer.fields["version"], serializers.CharField)
        assert isinstance(serializer.fields["database"], serializers.BooleanField)
        assert isinstance(serializer.fields["cache"], serializers.BooleanField)
        assert isinstance(serializer.fields["celery"], serializers.BooleanField)
        assert isinstance(serializer.fields["uptime"], serializers.CharField)
        assert isinstance(serializer.fields["memory_usage"], serializers.FloatField)
        assert isinstance(serializer.fields["cpu_usage"], serializers.FloatField)
        assert isinstance(serializer.fields["services"], serializers.DictField)
        assert isinstance(serializer.fields["errors"], serializers.ListField)

    def test_validation_invalid_data(self):
        """Test validation with invalid data types"""
        invalid_data = {
            "status": 123,  # Should be string
            "timestamp": "not-a-datetime",  # Should be datetime
            "database": "not-a-boolean",  # Should be boolean
            "cache": "not-a-boolean",  # Should be boolean
        }

        serializer = HealthCheckSerializer(data=invalid_data)
        assert not serializer.is_valid()
        assert "status" in serializer.errors or "timestamp" in serializer.errors

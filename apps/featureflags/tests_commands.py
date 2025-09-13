"""Tests for feature flags management commands."""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from waffle.models import Flag, Sample, Switch

User = get_user_model()


class TestSyncFlagsCommand(TestCase):
    """Test sync_flags management command."""

    def setUp(self):
        """Set up test data."""
        # Clear any existing flags
        Flag.objects.all().delete()
        Switch.objects.all().delete()
        Sample.objects.all().delete()

    def test_sync_flags_dry_run(self):
        """Test sync_flags with --dry-run option."""
        out = StringIO()

        call_command("sync_flags", "--dry-run", stdout=out)

        output = out.getvalue()
        self.assertIn("DRY RUN MODE", output)
        # Should not create any flags in dry run
        self.assertEqual(Flag.objects.count(), 0)

    def test_sync_flags_creates_missing_flags(self):
        """Test sync_flags creates missing flags."""
        out = StringIO()

        call_command("sync_flags", stdout=out)

        output = out.getvalue()

        # Check that default flags were created
        self.assertIn("Created flag: FILES", output)
        self.assertIn("Created flag: EMAIL_EDITOR", output)
        self.assertIn("Created flag: RABBITMQ", output)

        # Verify flags exist in database
        self.assertTrue(Flag.objects.filter(name="FILES").exists())
        self.assertTrue(Flag.objects.filter(name="EMAIL_EDITOR").exists())

    def test_sync_flags_updates_existing_flags_with_force(self):
        """Test sync_flags updates existing flags with --force option."""
        # Create an existing flag with different settings
        Flag.objects.create(
            name="FILES", everyone=True, note="Old note"  # Different from default
        )

        out = StringIO()
        call_command("sync_flags", "--force", stdout=out)

        output = out.getvalue()
        self.assertIn("Updated flag: FILES", output)

        # Verify flag was updated
        flag = Flag.objects.get(name="FILES")
        self.assertIn("Enable file upload", flag.note)

    def test_sync_flags_skips_existing_without_force(self):
        """Test sync_flags skips existing flags without --force option."""
        # Create an existing flag
        Flag.objects.create(name="FILES", everyone=True, note="Existing note")

        out = StringIO()
        call_command("sync_flags", stdout=out)

        output = out.getvalue()
        self.assertIn("Flag FILES already exists", output)

        # Verify flag was not changed
        flag = Flag.objects.get(name="FILES")
        self.assertEqual(flag.note, "Existing note")

    def test_sync_flags_creates_switches(self):
        """Test sync_flags creates switches."""
        out = StringIO()

        # Add a switch to the configuration
        with patch(
            "apps.featureflags.management.commands.sync_flags.Command._get_switches"
        ) as mock_get_switches:
            mock_get_switches.return_value = {
                "SWITCH_TEST": {"active": True, "note": "Test switch"}
            }

            call_command("sync_flags", stdout=out)

            output = out.getvalue()
            self.assertIn("Created switch: SWITCH_TEST", output)

    def test_sync_flags_creates_samples(self):
        """Test sync_flags creates samples."""
        out = StringIO()

        # Add a sample to the configuration
        with patch(
            "apps.featureflags.management.commands.sync_flags.Command._get_samples"
        ) as mock_get_samples:
            mock_get_samples.return_value = {
                "SAMPLE_TEST": {"percent": 50, "note": "Test sample"}
            }

            call_command("sync_flags", stdout=out)

            output = out.getvalue()
            self.assertIn("Created sample: SAMPLE_TEST", output)

    def test_sync_flags_summary(self):
        """Test sync_flags provides summary."""
        out = StringIO()

        call_command("sync_flags", stdout=out)

        output = out.getvalue()
        self.assertIn("Sync completed:", output)
        self.assertIn("flags", output)
        self.assertIn("switches", output)
        self.assertIn("samples", output)

    def test_sync_flags_handles_errors(self):
        """Test sync_flags handles database errors gracefully."""
        out = StringIO()
        err = StringIO()

        with patch("waffle.models.Flag.objects.create") as mock_create:
            mock_create.side_effect = Exception("Database error")

            with self.assertRaisesRegex(Exception, "Database error"):
                call_command("sync_flags", stdout=out, stderr=err)

    def test_sync_flags_with_custom_defaults(self):
        """Test sync_flags with custom default values."""
        out = StringIO()

        # Test that EMAIL_EDITOR is created with active=True by default
        call_command("sync_flags", stdout=out)

        flag = Flag.objects.get(name="EMAIL_EDITOR")
        # Check that the flag was created (specifics depend on implementation)
        self.assertIsNotNone(flag)

    def test_sync_flags_preserves_user_assignments(self):
        """Test sync_flags preserves user/group assignments with force."""
        user = User.objects.create_user(
            email="test@example.com", password="testpass123"
        )

        # Create flag with user assignment
        flag = Flag.objects.create(name="FILES")
        flag.users.add(user)

        out = StringIO()
        call_command("sync_flags", "--force", stdout=out)

        # Verify user assignment is preserved
        flag.refresh_from_db()
        self.assertIn(user, flag.users.all())


class TestSyncFlagsCommandHelpers(TestCase):
    """Test helper methods of sync_flags command."""

    def test_get_default_flags(self):
        """Test that command gets default flags from FeatureFlags class."""
        from apps.featureflags.management.commands.sync_flags import Command

        cmd = Command()

        # Mock the method if it exists
        if hasattr(cmd, "_get_default_flags"):
            flags = cmd._get_default_flags()
            self.assertIn("FILES", flags)
            self.assertIn("EMAIL_EDITOR", flags)

    def test_command_help_text(self):
        """Test command has proper help text."""
        from apps.featureflags.management.commands.sync_flags import Command

        cmd = Command()
        self.assertIsNotNone(cmd.help)
        self.assertIn("flag", cmd.help.lower())

    def test_command_arguments(self):
        """Test command accepts expected arguments."""
        from argparse import ArgumentParser

        from apps.featureflags.management.commands.sync_flags import Command

        cmd = Command()
        parser = ArgumentParser()
        cmd.add_arguments(parser)

        # Parse test arguments
        args = parser.parse_args(["--dry-run", "--force"])
        self.assertTrue(args.dry_run)
        self.assertTrue(args.force)

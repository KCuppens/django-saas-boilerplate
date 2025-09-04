from django.core.management.base import BaseCommand
from waffle.models import Flag, Switch

from apps.featureflags.helpers import FeatureFlags


class Command(BaseCommand):
    """Management command to sync feature flags"""

    help = "Sync feature flags with default configuration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without making changes",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force update existing flags",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        created_flags = 0
        updated_flags = 0

        for flag_name, flag_config in FeatureFlags.DEFAULT_FLAGS.items():
            flag, created = Flag.objects.get_or_create(
                name=flag_name,
                defaults={
                    "everyone": flag_config.get("default", False),
                    "note": flag_config.get("description", ""),
                },
            )

            if created:
                created_flags += 1
                self.stdout.write(self.style.SUCCESS(f"Created flag: {flag_name}"))
            elif force:
                updated_flags += 1
                if not dry_run:
                    flag.everyone = flag_config.get("default", False)
                    flag.note = flag_config.get("description", "")
                    flag.save()

                self.stdout.write(self.style.WARNING(f"Updated flag: {flag_name}"))
            else:
                self.stdout.write(
                    self.style.NOTICE(
                        f"Flag {flag_name} already exists (use --force to update)"
                    )
                )

        # Create some default switches
        default_switches = {
            "MAINTENANCE_MODE": {
                "active": False,
                "note": "Global maintenance mode switch",
            },
            "DEBUG_MODE": {"active": False, "note": "Debug mode for development"},
        }

        for switch_name, switch_config in default_switches.items():
            switch, created = Switch.objects.get_or_create(
                name=switch_name,
                defaults={
                    "active": switch_config["active"],
                    "note": switch_config["note"],
                },
            )

            if created:
                created_flags += 1
                self.stdout.write(self.style.SUCCESS(f"Created switch: {switch_name}"))
            elif force and not dry_run:
                switch.active = switch_config["active"]
                switch.note = switch_config["note"]
                switch.save()
                updated_flags += 1
                self.stdout.write(self.style.WARNING(f"Updated switch: {switch_name}"))

        # Summary
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSync completed: {created_flags} flags created, "
                    f"{updated_flags} flags updated"
                )
            )
        else:
            self.stdout.write(
                self.style.NOTICE(
                    f"\nDry run completed: would create {created_flags} flags, "
                    f"update {updated_flags} flags"
                )
            )

        # Show flag summary
        self.stdout.write("\nFlag Summary:")
        for flag_name, flag_config in FeatureFlags.DEFAULT_FLAGS.items():
            status = "✓" if flag_config.get("default", False) else "✗"
            self.stdout.write(
                f"  {status} {flag_name}: {flag_config.get('description', 'No description')}"
            )

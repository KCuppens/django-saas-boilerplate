from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Management command to sync user groups and their permissions"""

    help = "Sync user groups and their permissions"

    # Define group permissions mapping
    GROUP_PERMISSIONS = {
        "Admin": {
            "description": "Full system access",
            "permissions": [
                # User management
                "accounts.add_user",
                "accounts.change_user",
                "accounts.delete_user",
                "accounts.view_user",
                "accounts.add_userprofile",
                "accounts.change_userprofile",
                "accounts.delete_userprofile",
                "accounts.view_userprofile",
                # Group management
                "auth.add_group",
                "auth.change_group",
                "auth.delete_group",
                "auth.view_group",
                # Email templates
                "emails.add_emailtemplate",
                "emails.change_emailtemplate",
                "emails.delete_emailtemplate",
                "emails.view_emailtemplate",
                "emails.add_emailmessagelog",
                "emails.change_emailmessagelog",
                "emails.delete_emailmessagelog",
                "emails.view_emailmessagelog",
                # Feature flags (all waffle permissions)
                "waffle.add_flag",
                "waffle.change_flag",
                "waffle.delete_flag",
                "waffle.view_flag",
                "waffle.add_switch",
                "waffle.change_switch",
                "waffle.delete_switch",
                "waffle.view_switch",
                "waffle.add_sample",
                "waffle.change_sample",
                "waffle.delete_sample",
                "waffle.view_sample",
            ],
        },
        "Manager": {
            "description": "Management access with limited admin rights",
            "permissions": [
                # User management (limited)
                "accounts.change_user",
                "accounts.view_user",
                "accounts.view_userprofile",
                # Email templates (manage content)
                "emails.add_emailtemplate",
                "emails.change_emailtemplate",
                "emails.view_emailtemplate",
                "emails.view_emailmessagelog",
                # View groups
                "auth.view_group",
            ],
        },
        "Member": {
            "description": "Standard member access",
            "permissions": [
                # Own profile management
                "accounts.change_user",  # Limited to own user via permissions
                "accounts.view_user",  # Limited to own user via permissions
                "accounts.change_userprofile",
                "accounts.view_userprofile",
                # View email templates
                "emails.view_emailtemplate",
            ],
        },
        "ReadOnly": {
            "description": "Read-only access to most content",
            "permissions": [
                # View only permissions
                "accounts.view_user",
                "accounts.view_userprofile",
                "emails.view_emailtemplate",
                "auth.view_group",
            ],
        },
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed without making changes",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force update existing groups",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        created_groups = 0
        updated_groups = 0

        for group_name, group_config in self.GROUP_PERMISSIONS.items():
            group, created = Group.objects.get_or_create(name=group_name)

            if created:
                created_groups += 1
                self.stdout.write(self.style.SUCCESS(f"Created group: {group_name}"))
            elif force:
                updated_groups += 1
                self.stdout.write(self.style.WARNING(f"Updating group: {group_name}"))
            else:
                self.stdout.write(
                    self.style.NOTICE(
                        f"Group {group_name} already exists (use --force to update permissions)"
                    )
                )
                continue

            if not dry_run:
                # Clear existing permissions if updating
                if not created or force:
                    group.permissions.clear()

                # Add permissions
                permissions_added = 0
                for permission_codename in group_config["permissions"]:
                    try:
                        app_label, codename = permission_codename.split(".", 1)
                        permission = Permission.objects.get(
                            codename=codename, content_type__app_label=app_label
                        )
                        group.permissions.add(permission)
                        permissions_added += 1
                    except Permission.DoesNotExist:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Permission {permission_codename} not found"
                            )
                        )
                    except ValueError:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Invalid permission format: {permission_codename}"
                            )
                        )

                self.stdout.write(
                    f"  Added {permissions_added} permissions to {group_name}"
                )
            else:
                # Dry run - just show what would be added
                self.stdout.write(
                    f"  Would add {len(group_config['permissions'])} permissions to {group_name}"
                )
                for permission in group_config["permissions"]:
                    self.stdout.write(f"    - {permission}")

        # Summary
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSync completed: {created_groups} groups created, "
                    f"{updated_groups} groups updated"
                )
            )
        else:
            self.stdout.write(
                self.style.NOTICE(
                    f"\nDry run completed: would create {created_groups} groups, "
                    f"update {updated_groups} groups"
                )
            )

        # Show group summary
        self.stdout.write("\nGroup Summary:")
        for group_name, group_config in self.GROUP_PERMISSIONS.items():
            self.stdout.write(f"  {group_name}: {group_config['description']}")

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from apps.api.models import Note
from apps.emails.models import EmailTemplate

User = get_user_model()


class Command(BaseCommand):
    """Management command to seed demo data"""

    help = "Create demo users, groups, and sample data for development/testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo data before seeding",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="demo123",
            help="Password for demo users (default: demo123)",
        )
        parser.add_argument(
            "--skip-users",
            action="store_true",
            help="Skip creating demo users",
        )
        parser.add_argument(
            "--skip-templates",
            action="store_true",
            help="Skip creating email templates",
        )
        parser.add_argument(
            "--skip-notes",
            action="store_true",
            help="Skip creating demo notes",
        )

    def handle(self, *args, **options):
        reset = options["reset"]
        password = options["password"]
        skip_users = options["skip_users"]
        skip_templates = options["skip_templates"]
        skip_notes = options["skip_notes"]

        if reset:
            self.stdout.write(self.style.WARNING("Resetting demo data..."))
            self._reset_demo_data()

        # Create demo users
        if not skip_users:
            self._create_demo_users(password)

        # Create email templates
        if not skip_templates:
            self._create_email_templates()

        # Create sample notes
        if not skip_notes:
            self._create_demo_notes()

        self.stdout.write(
            self.style.SUCCESS("Demo data seeding completed successfully!")
        )

        # Show summary
        self._show_summary()

    def _reset_demo_data(self):
        """Delete existing demo data"""
        # Delete demo users (except superusers)
        demo_emails = [
            "admin@example.com",
            "manager@example.com",
            "member@example.com",
            "readonly@example.com",
        ]

        deleted_users = User.objects.filter(
            email__in=demo_emails, is_superuser=False
        ).delete()[0]

        if deleted_users > 0:
            self.stdout.write(f"Deleted {deleted_users} demo users")

        # Delete demo notes
        deleted_notes = Note.objects.filter(title__startswith="Demo:").delete()[0]

        if deleted_notes > 0:
            self.stdout.write(f"Deleted {deleted_notes} demo notes")

    def _create_demo_users(self, password):
        """Create demo users with different roles"""
        demo_users = [
            {
                "email": "admin@example.com",
                "name": "Demo Admin",
                "group": "Admin",
                "is_staff": True,
            },
            {
                "email": "manager@example.com",
                "name": "Demo Manager",
                "group": "Manager",
                "is_staff": False,
            },
            {
                "email": "member@example.com",
                "name": "Demo Member",
                "group": "Member",
                "is_staff": False,
            },
            {
                "email": "readonly@example.com",
                "name": "Demo ReadOnly",
                "group": "ReadOnly",
                "is_staff": False,
            },
        ]

        created_count = 0

        for user_data in demo_users:
            user, created = User.objects.get_or_create(
                email=user_data["email"],
                defaults={
                    "name": user_data["name"],
                    "is_staff": user_data["is_staff"],
                    "is_active": True,
                },
            )

            if created:
                user.set_password(password)
                user.save()
                created_count += 1

                # Add to group
                try:
                    group = Group.objects.get(name=user_data["group"])
                    user.groups.add(group)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Created user: {user.email} (Group: {user_data['group']})"
                        )
                    )
                except Group.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Group {user_data['group']} not found. Run sync_groups first."
                        )
                    )
            else:
                self.stdout.write(
                    self.style.NOTICE(f"User {user.email} already exists")
                )

        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(f"Created {created_count} demo users"))
            self.stdout.write(f"Demo user password: {password}")

    def _create_email_templates(self):
        """Create demo email templates"""
        templates = [
            {
                "key": "welcome",
                "name": "Welcome Email",
                "description": "Welcome email for new users",
                "category": "user",
                "subject": "Welcome to {{ site_name }}!",
                "html_content": """
<h2>Welcome {{ user_name }}!</h2>
<p>Thank you for joining {{ site_name }}. We're excited to have you on board!</p>
<p>Here are some things you can do to get started:</p>
<ul>
    <li><a href="{{ login_url }}">Log in to your account</a></li>
    <li>Complete your profile</li>
    <li>Explore our features</li>
</ul>
<p>If you have any questions, feel free to contact us at {{ support_email }}.</p>
<p>Best regards,<br>The {{ site_name }} Team</p>
                """,
                "text_content": """
Welcome {{ user_name }}!

Thank you for joining {{ site_name }}. We're excited to have you on board!

Here are some things you can do to get started:
- Log in to your account: {{ login_url }}
- Complete your profile
- Explore our features

If you have any questions, feel free to contact us at {{ support_email }}.

Best regards,
The {{ site_name }} Team
                """,
                "template_variables": {
                    "user_name": "User full name",
                    "site_name": "Site name",
                    "login_url": "Login URL",
                    "support_email": "Support email address",
                },
            },
            {
                "key": "password_reset",
                "name": "Password Reset",
                "description": "Password reset email",
                "category": "user",
                "subject": "Reset your password for {{ site_name }}",
                "html_content": """
<h2>Password Reset Request</h2>
<p>Hi {{ user_name }},</p>
<p>You requested a password reset for your {{ site_name }} account.</p>
<p><a href="{{ reset_link }}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Your Password</a></p>
<p>This link will expire in 24 hours. If you didn't request this reset, please ignore this email.</p>
<p>Best regards,<br>The {{ site_name }} Team</p>
                """,
                "text_content": """
Password Reset Request

Hi {{ user_name }},

You requested a password reset for your {{ site_name }} account.

Click this link to reset your password: {{ reset_link }}

This link will expire in 24 hours. If you didn't request this reset, please ignore this email.

Best regards,
The {{ site_name }} Team
                """,
                "template_variables": {
                    "user_name": "User full name",
                    "site_name": "Site name",
                    "reset_link": "Password reset link",
                },
            },
            {
                "key": "notification",
                "name": "General Notification",
                "description": "General notification email template",
                "category": "system",
                "subject": "{{ title }}",
                "html_content": """
<h2>{{ title }}</h2>
<p>Hi {{ user_name }},</p>
<p>{{ message }}</p>
{% if action_url %}
<p><a href="{{ action_url }}" style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Take Action</a></p>
{% endif %}
<p>Best regards,<br>The {{ site_name }} Team</p>
                """,
                "text_content": """
{{ title }}

Hi {{ user_name }},

{{ message }}

{% if action_url %}
Take action: {{ action_url }}
{% endif %}

Best regards,
The {{ site_name }} Team
                """,
                "template_variables": {
                    "title": "Notification title",
                    "user_name": "User full name",
                    "message": "Notification message",
                    "action_url": "Optional action URL",
                    "site_name": "Site name",
                },
            },
        ]

        created_count = 0

        for template_data in templates:
            template, created = EmailTemplate.objects.get_or_create(
                key=template_data["key"], defaults=template_data
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Created email template: {template.name}")
                )
            else:
                self.stdout.write(
                    self.style.NOTICE(f"Email template {template.key} already exists")
                )

        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"Created {created_count} email templates")
            )

    def _create_demo_notes(self):
        """Create demo notes"""
        try:
            demo_user = User.objects.get(email="member@example.com")
        except User.DoesNotExist:
            self.stdout.write(
                self.style.WARNING("Demo user not found, skipping notes creation")
            )
            return

        demo_notes = [
            {
                "title": "Demo: Welcome to the API",
                "content": "This is a sample note to demonstrate the Notes API functionality. You can create, update, and delete notes through the REST API.",
                "is_public": True,
                "tags": "demo, api, welcome",
            },
            {
                "title": "Demo: Private Note",
                "content": "This is a private note that only the creator can see. Perfect for storing personal information or drafts.",
                "is_public": False,
                "tags": "demo, private",
            },
            {
                "title": "Demo: Feature Ideas",
                "content": "Here are some feature ideas for the application:\n- Real-time notifications\n- File attachments\n- Collaborative editing\n- Export functionality",
                "is_public": True,
                "tags": "demo, features, ideas",
            },
        ]

        created_count = 0

        for note_data in demo_notes:
            note, created = Note.objects.get_or_create(
                title=note_data["title"],
                defaults={
                    **note_data,
                    "created_by": demo_user,
                    "updated_by": demo_user,
                },
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created note: {note.title}"))
            else:
                self.stdout.write(
                    self.style.NOTICE(f'Note "{note.title}" already exists')
                )

        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(f"Created {created_count} demo notes"))

    def _show_summary(self):
        """Show summary of created data"""
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("DEMO DATA SUMMARY")
        self.stdout.write("=" * 50)

        # Users
        user_count = User.objects.filter(email__endswith="@example.com").count()
        self.stdout.write(f"Demo users: {user_count}")

        # Email templates
        template_count = EmailTemplate.objects.count()
        self.stdout.write(f"Email templates: {template_count}")

        # Notes
        note_count = Note.objects.filter(title__startswith="Demo:").count()
        self.stdout.write(f"Demo notes: {note_count}")

        # Groups
        group_count = Group.objects.count()
        self.stdout.write(f"User groups: {group_count}")

        self.stdout.write("\n" + "LOGIN CREDENTIALS:")
        self.stdout.write("Email: admin@example.com | Password: demo123 (Admin)")
        self.stdout.write("Email: manager@example.com | Password: demo123 (Manager)")
        self.stdout.write("Email: member@example.com | Password: demo123 (Member)")
        self.stdout.write("Email: readonly@example.com | Password: demo123 (ReadOnly)")

        self.stdout.write("\n" + "API ENDPOINTS:")
        self.stdout.write("Health: http://localhost:8000/healthz")
        self.stdout.write("API Schema: http://localhost:8000/schema/swagger/")
        self.stdout.write(
            "User Registration: POST http://localhost:8000/api/v1/auth/users/register/"
        )
        self.stdout.write("Notes API: http://localhost:8000/api/v1/notes/")

        if EmailTemplate.objects.exists():
            self.stdout.write("\n" + "EMAIL TEMPLATES (Development only):")
            self.stdout.write("Template List: http://localhost:8000/dev/emails/")
            self.stdout.write(
                "Welcome Preview: http://localhost:8000/dev/emails/welcome/html/"
            )

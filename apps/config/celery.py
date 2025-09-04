import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'apps.config.settings.local')

app = Celery('django-saas-boilerplate')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat Schedule
app.conf.beat_schedule = {
    'cleanup-expired-sessions': {
        'task': 'apps.core.tasks.cleanup_expired_sessions',
        'schedule': 60.0 * 60.0 * 24.0,  # Daily
    },
    'backup-database': {
        'task': 'apps.ops.tasks.backup_database',
        'schedule': 60.0 * 60.0 * 24.0,  # Daily at midnight
        'options': {'expires': 60.0 * 60.0 * 2.0}  # Expire after 2 hours
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
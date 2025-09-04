"""Prometheus metrics for the application"""

from django.http import HttpResponse
from django.db import connection
from django.contrib.auth import get_user_model
from apps.api.models import Note
from apps.emails.models import EmailMessageLog
import time
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


def prometheus_metrics(request):
    """Prometheus metrics endpoint"""
    
    metrics = []
    
    # Add application metrics
    try:
        # User metrics
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        
        metrics.extend([
            f'# HELP django_users_total Total number of users',
            f'# TYPE django_users_total counter',
            f'django_users_total {total_users}',
            f'',
            f'# HELP django_users_active Number of active users', 
            f'# TYPE django_users_active gauge',
            f'django_users_active {active_users}',
            f''
        ])
        
        # Note metrics
        try:
            total_notes = Note.objects.count()
            public_notes = Note.objects.filter(is_public=True).count()
            
            metrics.extend([
                f'# HELP django_notes_total Total number of notes',
                f'# TYPE django_notes_total counter', 
                f'django_notes_total {total_notes}',
                f'',
                f'# HELP django_notes_public Number of public notes',
                f'# TYPE django_notes_public gauge',
                f'django_notes_public {public_notes}',
                f''
            ])
        except Exception as e:
            logger.warning(f"Failed to collect notes metrics: {e}")
        
        # Email metrics
        try:
            total_emails = EmailMessageLog.objects.count()
            sent_emails = EmailMessageLog.objects.filter(status='sent').count()
            failed_emails = EmailMessageLog.objects.filter(status='failed').count()
            
            metrics.extend([
                f'# HELP django_emails_total Total number of emails',
                f'# TYPE django_emails_total counter',
                f'django_emails_total {total_emails}',
                f'',
                f'# HELP django_emails_sent Number of sent emails',
                f'# TYPE django_emails_sent counter', 
                f'django_emails_sent {sent_emails}',
                f'',
                f'# HELP django_emails_failed Number of failed emails',
                f'# TYPE django_emails_failed counter',
                f'django_emails_failed {failed_emails}',
                f''
            ])
        except Exception as e:
            logger.warning(f"Failed to collect notes metrics: {e}")
        
        # Database connection metrics
        try:
            db_start = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            db_duration = time.time() - db_start
            
            metrics.extend([
                f'# HELP django_db_connection_duration_seconds Database connection duration',
                f'# TYPE django_db_connection_duration_seconds histogram',
                f'django_db_connection_duration_seconds {db_duration:.6f}',
                f''
            ])
        except Exception as e:
            logger.warning(f"Failed to collect notes metrics: {e}")
        
        # Cache metrics (if Redis/cache available)
        try:
            from django.core.cache import cache
            cache_start = time.time()
            cache.set('metrics_test', 'ok', 10)
            cache_result = cache.get('metrics_test')
            cache_duration = time.time() - cache_start
            
            cache_status = 1 if cache_result == 'ok' else 0
            
            metrics.extend([
                f'# HELP django_cache_status Cache availability status',
                f'# TYPE django_cache_status gauge',
                f'django_cache_status {cache_status}',
                f'',
                f'# HELP django_cache_duration_seconds Cache operation duration',
                f'# TYPE django_cache_duration_seconds histogram', 
                f'django_cache_duration_seconds {cache_duration:.6f}',
                f''
            ])
        except Exception as e:
            logger.warning(f"Failed to collect notes metrics: {e}")
        
        # System uptime (approximate)
        try:
            import psutil
            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available = memory.available
            memory_total = memory.total
            
            # CPU usage  
            cpu_percent = psutil.cpu_percent()
            
            metrics.extend([
                f'# HELP system_uptime_seconds System uptime in seconds',
                f'# TYPE system_uptime_seconds counter',
                f'system_uptime_seconds {uptime:.0f}',
                f'',
                f'# HELP system_memory_usage_percent Memory usage percentage',
                f'# TYPE system_memory_usage_percent gauge',
                f'system_memory_usage_percent {memory_percent}',
                f'',
                f'# HELP system_memory_available_bytes Available memory in bytes',
                f'# TYPE system_memory_available_bytes gauge', 
                f'system_memory_available_bytes {memory_available}',
                f'',
                f'# HELP system_memory_total_bytes Total memory in bytes',
                f'# TYPE system_memory_total_bytes gauge',
                f'system_memory_total_bytes {memory_total}',
                f'',
                f'# HELP system_cpu_usage_percent CPU usage percentage',
                f'# TYPE system_cpu_usage_percent gauge',
                f'system_cpu_usage_percent {cpu_percent}',
                f''
            ])
        except ImportError:
            # psutil not available
            pass
        except Exception as e:
            logger.warning(f"Failed to collect notes metrics: {e}")
    
    except Exception as e:
        # Fallback metrics if database is unavailable
        metrics = [
            f'# HELP django_app_status Application status',
            f'# TYPE django_app_status gauge', 
            f'django_app_status 0',
            f'',
            f'# Error: {str(e)}'
        ]
    
    # Add timestamp
    metrics.extend([
        f'# HELP django_metrics_timestamp Last metrics collection timestamp',
        f'# TYPE django_metrics_timestamp gauge',
        f'django_metrics_timestamp {int(time.time())}'
    ])
    
    return HttpResponse(
        '\n'.join(metrics),
        content_type='text/plain; version=0.0.4; charset=utf-8'
    )


def health_metrics(request):
    """Simple health metrics for monitoring"""
    
    metrics = {
        'status': 'healthy',
        'timestamp': int(time.time()),
        'checks': {}
    }
    
    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        metrics['checks']['database'] = True
    except:
        metrics['checks']['database'] = False
        metrics['status'] = 'unhealthy'
    
    # Cache check
    try:
        from django.core.cache import cache
        cache.set('health_check', 'ok', 10)
        metrics['checks']['cache'] = cache.get('health_check') == 'ok'
    except:
        metrics['checks']['cache'] = False
    
    # Overall status
    if not all(metrics['checks'].values()):
        metrics['status'] = 'degraded'
    
    # Convert to Prometheus format
    prometheus_metrics = [
        f'# HELP django_health_status Application health status (1=healthy, 0=unhealthy)',
        f'# TYPE django_health_status gauge',
        f'django_health_status {1 if metrics["status"] == "healthy" else 0}',
        f'',
        f'# HELP django_health_database Database health status',
        f'# TYPE django_health_database gauge',
        f'django_health_database {1 if metrics["checks"]["database"] else 0}',
        f'',
        f'# HELP django_health_cache Cache health status',
        f'# TYPE django_health_cache gauge', 
        f'django_health_cache {1 if metrics["checks"]["cache"] else 0}',
        f'',
        f'# HELP django_health_timestamp Health check timestamp',
        f'# TYPE django_health_timestamp gauge',
        f'django_health_timestamp {metrics["timestamp"]}'
    ]
    
    return HttpResponse(
        '\n'.join(prometheus_metrics),
        content_type='text/plain; version=0.0.4; charset=utf-8'
    )
from celery import shared_task
import subprocess
import os
import datetime
from django.conf import settings
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)


@shared_task(name='apps.ops.tasks.backup_database')
def backup_database():
    """Backup database to file"""
    try:
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"backup_{timestamp}.sql"
        backup_path = os.path.join(settings.BASE_DIR, 'backups', backup_filename)
        
        # Ensure backup directory exists
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        # Get database config
        db_config = settings.DATABASES['default']
        
        if db_config['ENGINE'] == 'django.db.backends.postgresql':
            # PostgreSQL backup
            cmd = [
                'pg_dump',
                '--host', db_config.get('HOST', 'localhost'),
                '--port', str(db_config.get('PORT', 5432)),
                '--username', db_config['USER'],
                '--no-password',
                '--format', 'custom',
                '--file', backup_path,
                db_config['NAME']
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = db_config['PASSWORD']
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Database backup created successfully: {backup_path}")
                return {
                    'success': True,
                    'backup_file': backup_filename,
                    'backup_path': backup_path,
                    'timestamp': timestamp
                }
            else:
                logger.error(f"Database backup failed: {result.stderr}")
                return {
                    'success': False,
                    'error': result.stderr
                }
        
        else:
            # For SQLite or other databases, use Django's dumpdata
            with open(backup_path, 'w') as f:
                call_command('dumpdata', stdout=f, indent=2)
            
            logger.info(f"Database backup created successfully: {backup_path}")
            return {
                'success': True,
                'backup_file': backup_filename,
                'backup_path': backup_path,
                'timestamp': timestamp
            }
    
    except Exception as e:
        logger.error(f"Database backup failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='apps.ops.tasks.cleanup_old_backups')
def cleanup_old_backups(days_to_keep=7):
    """Clean up old backup files"""
    try:
        import glob
        from pathlib import Path
        
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        
        if not os.path.exists(backup_dir):
            return {
                'success': True,
                'cleaned_files': 0,
                'message': 'Backup directory does not exist'
            }
        
        # Find backup files older than specified days
        cutoff_time = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
        
        backup_files = glob.glob(os.path.join(backup_dir, 'backup_*.sql'))
        cleaned_count = 0
        
        for backup_file in backup_files:
            file_stat = os.stat(backup_file)
            file_time = datetime.datetime.fromtimestamp(file_stat.st_mtime)
            
            if file_time < cutoff_time:
                os.remove(backup_file)
                cleaned_count += 1
                logger.info(f"Removed old backup: {backup_file}")
        
        logger.info(f"Cleaned up {cleaned_count} old backup files")
        
        return {
            'success': True,
            'cleaned_files': cleaned_count,
            'days_kept': days_to_keep
        }
    
    except Exception as e:
        logger.error(f"Backup cleanup failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='apps.ops.tasks.system_maintenance')
def system_maintenance():
    """Perform system maintenance tasks"""
    try:
        results = {}
        
        # Clear expired sessions
        try:
            call_command('clearsessions')
            results['clear_sessions'] = True
        except Exception as e:
            results['clear_sessions'] = f"Error: {str(e)}"
        
        # Collect static files (if in production)
        if not settings.DEBUG:
            try:
                call_command('collectstatic', '--noinput', '--clear')
                results['collect_static'] = True
            except Exception as e:
                results['collect_static'] = f"Error: {str(e)}"
        
        # Clear cache
        try:
            from django.core.cache import cache
            cache.clear()
            results['clear_cache'] = True
        except Exception as e:
            results['clear_cache'] = f"Error: {str(e)}"
        
        logger.info("System maintenance completed")
        
        return {
            'success': True,
            'maintenance_results': results,
            'timestamp': datetime.datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"System maintenance failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='apps.ops.tasks.health_check_task')
def health_check_task():
    """Periodic health check task"""
    try:
        results = {
            'timestamp': datetime.datetime.now().isoformat(),
            'checks': {}
        }
        
        # Check database
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            results['checks']['database'] = True
        except Exception as e:
            results['checks']['database'] = f"Error: {str(e)}"
        
        # Check cache
        try:
            from django.core.cache import cache
            test_key = 'health_check_test'
            cache.set(test_key, 'ok', 30)
            cache_result = cache.get(test_key)
            results['checks']['cache'] = cache_result == 'ok'
        except Exception as e:
            results['checks']['cache'] = f"Error: {str(e)}"
        
        # Check disk space
        try:
            import shutil
            disk_usage = shutil.disk_usage(settings.BASE_DIR)
            free_gb = disk_usage.free / (1024**3)
            results['checks']['disk_space'] = {
                'free_gb': round(free_gb, 2),
                'sufficient': free_gb > 1.0  # At least 1GB free
            }
        except Exception as e:
            results['checks']['disk_space'] = f"Error: {str(e)}"
        
        # Determine overall health
        all_healthy = True
        for check_name, check_result in results['checks'].items():
            if isinstance(check_result, dict):
                if not check_result.get('sufficient', True):
                    all_healthy = False
            elif check_result is not True:
                all_healthy = False
        
        results['overall_health'] = 'healthy' if all_healthy else 'unhealthy'
        
        if all_healthy:
            logger.info("Health check passed")
        else:
            logger.warning(f"Health check failed: {results}")
        
        return {
            'success': True,
            'health_results': results
        }
    
    except Exception as e:
        logger.error(f"Health check task failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
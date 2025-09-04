#!/bin/bash

# Database backup script for Django SaaS Boilerplate
# This script creates a backup of the PostgreSQL database

set -e  # Exit on any error

# Default configuration
BACKUP_DIR="${BACKUP_DIR:-$(dirname "$0")/../backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="backup_${TIMESTAMP}.sql"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

# Database configuration from environment or defaults
DB_NAME="${DATABASE_NAME:-django_saas}"
DB_USER="${DATABASE_USER:-django}"
DB_HOST="${DATABASE_HOST:-localhost}"
DB_PORT="${DATABASE_PORT:-5432}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
Database Backup Script

Usage: $0 [OPTIONS]

OPTIONS:
    -h, --help          Show this help message
    -d, --dir DIR       Backup directory (default: ./backups)
    -r, --retention N   Keep backups for N days (default: 7)
    -n, --name NAME     Database name (default: django_saas)
    --dry-run          Show what would be done without executing

ENVIRONMENT VARIABLES:
    DATABASE_NAME       Database name
    DATABASE_USER       Database user
    DATABASE_HOST       Database host
    DATABASE_PORT       Database port
    PGPASSWORD         Database password (recommended way to pass password)
    BACKUP_DIR         Backup directory
    RETENTION_DAYS     Number of days to keep backups

EXAMPLES:
    $0                                 # Basic backup with defaults
    $0 -d /var/backups -r 30          # Custom directory and retention
    PGPASSWORD=secret $0 -n mydb      # With password and custom DB name
    $0 --dry-run                      # Preview what would be done

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        -r|--retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        -n|--name)
            DB_NAME="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check if PostgreSQL client tools are available
if ! command -v pg_dump &> /dev/null; then
    log_error "pg_dump not found. Please install PostgreSQL client tools."
    exit 1
fi

# Create backup directory if it doesn't exist
if [[ -z "$DRY_RUN" ]]; then
    mkdir -p "$BACKUP_DIR"
    if [[ ! -d "$BACKUP_DIR" ]]; then
        log_error "Cannot create backup directory: $BACKUP_DIR"
        exit 1
    fi
fi

BACKUP_PATH="$BACKUP_DIR/$BACKUP_FILE"

log_info "Starting database backup..."
log_info "Database: $DB_NAME"
log_info "Host: $DB_HOST:$DB_PORT"
log_info "User: $DB_USER"
log_info "Backup file: $BACKUP_PATH"
log_info "Retention: $RETENTION_DAYS days"

if [[ -n "$DRY_RUN" ]]; then
    log_warn "DRY RUN MODE - No actual backup will be performed"
    log_info "Would execute: pg_dump --host $DB_HOST --port $DB_PORT --username $DB_USER --no-password --format custom --file $BACKUP_PATH $DB_NAME"
else
    # Perform the backup
    log_info "Creating backup..."
    
    if pg_dump \
        --host "$DB_HOST" \
        --port "$DB_PORT" \
        --username "$DB_USER" \
        --no-password \
        --format custom \
        --file "$BACKUP_PATH" \
        "$DB_NAME"; then
        
        # Check if backup file was created and has content
        if [[ -f "$BACKUP_PATH" && -s "$BACKUP_PATH" ]]; then
            BACKUP_SIZE=$(du -h "$BACKUP_PATH" | cut -f1)
            log_info "Backup completed successfully!"
            log_info "Backup file: $BACKUP_PATH"
            log_info "Backup size: $BACKUP_SIZE"
        else
            log_error "Backup file is empty or was not created"
            exit 1
        fi
    else
        log_error "Backup failed!"
        exit 1
    fi
fi

# Cleanup old backups
if [[ "$RETENTION_DAYS" -gt 0 ]]; then
    log_info "Cleaning up backups older than $RETENTION_DAYS days..."
    
    if [[ -n "$DRY_RUN" ]]; then
        log_info "Would remove files older than $RETENTION_DAYS days from $BACKUP_DIR"
        find "$BACKUP_DIR" -name "backup_*.sql" -type f -mtime +$RETENTION_DAYS -print | while read -r file; do
            log_info "Would remove: $file"
        done
    else
        REMOVED_COUNT=0
        find "$BACKUP_DIR" -name "backup_*.sql" -type f -mtime +$RETENTION_DAYS -print0 | while IFS= read -r -d '' file; do
            log_info "Removing old backup: $(basename "$file")"
            rm "$file"
            ((REMOVED_COUNT++))
        done
        
        if [[ $REMOVED_COUNT -gt 0 ]]; then
            log_info "Removed $REMOVED_COUNT old backup files"
        else
            log_info "No old backup files to remove"
        fi
    fi
fi

# Summary
if [[ -z "$DRY_RUN" ]]; then
    log_info "Backup process completed successfully!"
    
    # List current backups
    log_info "Current backups in $BACKUP_DIR:"
    ls -lah "$BACKUP_DIR"/backup_*.sql 2>/dev/null | while read -r line; do
        log_info "  $line"
    done || log_info "  No backup files found"
else
    log_info "Dry run completed - no changes made"
fi

exit 0
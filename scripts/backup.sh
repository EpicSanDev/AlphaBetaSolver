#!/bin/bash
# Backup and disaster recovery script for GTO Poker Solver

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
S3_BUCKET="${S3_BUCKET:-gto-solver-backups}"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Database backup
backup_database() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_file="${BACKUP_DIR}/database_${timestamp}.sql"
    
    print_status "Starting database backup..."
    
    # Create backup directory if it doesn't exist
    mkdir -p "${BACKUP_DIR}"
    
    # Perform database backup
    docker exec gto-postgres pg_dump -U gto_user -d gto_solver > "${backup_file}"
    
    # Compress the backup
    gzip "${backup_file}"
    backup_file="${backup_file}.gz"
    
    # Encrypt if encryption key is provided
    if [[ -n "${ENCRYPTION_KEY}" ]]; then
        print_status "Encrypting database backup..."
        openssl enc -aes-256-cbc -salt -in "${backup_file}" -out "${backup_file}.enc" -k "${ENCRYPTION_KEY}"
        rm "${backup_file}"
        backup_file="${backup_file}.enc"
    fi
    
    print_status "Database backup completed: ${backup_file}"
    echo "${backup_file}"
}

# Application data backup
backup_application_data() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_file="${BACKUP_DIR}/app_data_${timestamp}.tar.gz"
    
    print_status "Starting application data backup..."
    
    # Create backup directory if it doesn't exist
    mkdir -p "${BACKUP_DIR}"
    
    # Backup application data (logs, simulation results, etc.)
    tar -czf "${backup_file}" \
        --exclude='*.tmp' \
        --exclude='*.log' \
        data/ logs/ || true
    
    # Encrypt if encryption key is provided
    if [[ -n "${ENCRYPTION_KEY}" ]]; then
        print_status "Encrypting application data backup..."
        openssl enc -aes-256-cbc -salt -in "${backup_file}" -out "${backup_file}.enc" -k "${ENCRYPTION_KEY}"
        rm "${backup_file}"
        backup_file="${backup_file}.enc"
    fi
    
    print_status "Application data backup completed: ${backup_file}"
    echo "${backup_file}"
}

# Configuration backup
backup_configuration() {
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_file="${BACKUP_DIR}/config_${timestamp}.tar.gz"
    
    print_status "Starting configuration backup..."
    
    # Create backup directory if it doesn't exist
    mkdir -p "${BACKUP_DIR}"
    
    # Backup configuration files
    tar -czf "${backup_file}" \
        docker-compose.yml \
        .env* \
        nginx.conf \
        monitoring/ \
        scripts/ || true
    
    # Encrypt if encryption key is provided
    if [[ -n "${ENCRYPTION_KEY}" ]]; then
        print_status "Encrypting configuration backup..."
        openssl enc -aes-256-cbc -salt -in "${backup_file}" -out "${backup_file}.enc" -k "${ENCRYPTION_KEY}"
        rm "${backup_file}"
        backup_file="${backup_file}.enc"
    fi
    
    print_status "Configuration backup completed: ${backup_file}"
    echo "${backup_file}"
}

# Upload to cloud storage
upload_to_cloud() {
    local file="$1"
    
    if [[ -z "${S3_BUCKET}" ]]; then
        print_warning "S3_BUCKET not configured, skipping cloud upload"
        return
    fi
    
    print_status "Uploading ${file} to cloud storage..."
    
    # Check if AWS CLI is available
    if command -v aws &> /dev/null; then
        aws s3 cp "${file}" "s3://${S3_BUCKET}/" || {
            print_error "Failed to upload to S3"
            return 1
        }
        print_status "Successfully uploaded to S3"
    else
        print_warning "AWS CLI not available, skipping cloud upload"
    fi
}

# Clean old backups
cleanup_old_backups() {
    print_status "Cleaning up old backups (older than ${RETENTION_DAYS} days)..."
    
    find "${BACKUP_DIR}" -name "*.sql.gz*" -mtime +${RETENTION_DAYS} -delete || true
    find "${BACKUP_DIR}" -name "*.tar.gz*" -mtime +${RETENTION_DAYS} -delete || true
    
    print_status "Old backup cleanup completed"
}

# Restore database
restore_database() {
    local backup_file="$1"
    
    if [[ -z "${backup_file}" ]]; then
        print_error "Please specify a backup file to restore"
        exit 1
    fi
    
    if [[ ! -f "${backup_file}" ]]; then
        print_error "Backup file not found: ${backup_file}"
        exit 1
    fi
    
    print_warning "This will overwrite the current database. Are you sure? (y/N)"
    read -r confirm
    if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
        print_info "Restore cancelled"
        exit 0
    fi
    
    print_status "Starting database restore from ${backup_file}..."
    
    # Decrypt if needed
    local restore_file="${backup_file}"
    if [[ "${backup_file}" == *.enc ]]; then
        if [[ -z "${ENCRYPTION_KEY}" ]]; then
            print_error "Backup is encrypted but no encryption key provided"
            exit 1
        fi
        
        restore_file="${backup_file%.enc}"
        openssl enc -aes-256-cbc -d -in "${backup_file}" -out "${restore_file}" -k "${ENCRYPTION_KEY}"
    fi
    
    # Decompress if needed
    if [[ "${restore_file}" == *.gz ]]; then
        gunzip -c "${restore_file}" > "${restore_file%.gz}"
        restore_file="${restore_file%.gz}"
    fi
    
    # Stop the application
    print_status "Stopping application..."
    docker-compose stop master-node compute-node-1 compute-node-2 || true
    
    # Drop and recreate database
    print_status "Recreating database..."
    docker exec gto-postgres psql -U gto_user -d postgres -c "DROP DATABASE IF EXISTS gto_solver;"
    docker exec gto-postgres psql -U gto_user -d postgres -c "CREATE DATABASE gto_solver;"
    
    # Restore database
    print_status "Restoring database..."
    docker exec -i gto-postgres psql -U gto_user -d gto_solver < "${restore_file}"
    
    # Clean up temporary files
    if [[ "${restore_file}" != "${backup_file}" ]]; then
        rm -f "${restore_file}"
    fi
    
    # Restart the application
    print_status "Restarting application..."
    docker-compose up -d
    
    print_status "Database restore completed successfully!"
}

# Health check before backup
health_check() {
    print_status "Performing health check..."
    
    # Check if containers are running
    if ! docker-compose ps | grep -q "Up"; then
        print_error "Some containers are not running"
        return 1
    fi
    
    # Check database connectivity
    if ! docker exec gto-postgres pg_isready -U gto_user &> /dev/null; then
        print_error "Database is not accessible"
        return 1
    fi
    
    # Check API health
    if ! curl -f http://localhost:8000/api/v1/health &> /dev/null; then
        print_warning "API health check failed, but continuing with backup"
    fi
    
    print_status "Health check passed"
}

# Full backup
full_backup() {
    print_status "Starting full backup..."
    
    # Health check
    health_check || {
        print_error "Health check failed, aborting backup"
        exit 1
    }
    
    # Create timestamped backup directory
    local timestamp=$(date +"%Y%m%d_%H%M%S")
    local backup_session_dir="${BACKUP_DIR}/full_backup_${timestamp}"
    mkdir -p "${backup_session_dir}"
    
    # Set BACKUP_DIR for this session
    export BACKUP_DIR="${backup_session_dir}"
    
    # Perform backups
    local db_backup=$(backup_database)
    local data_backup=$(backup_application_data)
    local config_backup=$(backup_configuration)
    
    # Create manifest
    cat > "${backup_session_dir}/manifest.txt" << EOF
GTO Poker Solver Full Backup
Timestamp: ${timestamp}
Created: $(date)

Files:
- Database: $(basename "${db_backup}")
- Application Data: $(basename "${data_backup}")
- Configuration: $(basename "${config_backup}")

Checksums:
$(cd "${backup_session_dir}" && sha256sum *.gz* *.enc 2>/dev/null || true)
EOF
    
    # Upload to cloud if configured
    for file in "${db_backup}" "${data_backup}" "${config_backup}"; do
        upload_to_cloud "${file}" || true
    done
    
    # Upload manifest
    upload_to_cloud "${backup_session_dir}/manifest.txt" || true
    
    print_status "Full backup completed in ${backup_session_dir}"
    
    # Cleanup old backups
    cleanup_old_backups
}

# Point-in-time recovery
point_in_time_recovery() {
    local target_time="$1"
    
    if [[ -z "${target_time}" ]]; then
        print_error "Please specify target time for recovery (YYYY-MM-DD HH:MM:SS)"
        exit 1
    fi
    
    print_status "Starting point-in-time recovery to ${target_time}"
    
    # Find the latest backup before the target time
    local backup_file=$(find "${BACKUP_DIR}" -name "database_*.sql.gz*" -newermt "${target_time}" | sort | head -1)
    
    if [[ -z "${backup_file}" ]]; then
        print_error "No suitable backup found for point-in-time recovery"
        exit 1
    fi
    
    print_status "Using backup: ${backup_file}"
    restore_database "${backup_file}"
}

# Disaster recovery
disaster_recovery() {
    print_status "Starting disaster recovery procedure..."
    
    # Check if this is a fresh environment
    if docker-compose ps &> /dev/null; then
        print_warning "Existing environment detected. This will be completely reset."
        print_warning "Are you sure you want to continue? (y/N)"
        read -r confirm
        if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
            print_info "Disaster recovery cancelled"
            exit 0
        fi
    fi
    
    # Stop and remove all containers
    print_status "Stopping and removing all containers..."
    docker-compose down -v || true
    
    # Remove all GTO solver containers and volumes
    docker ps -a | grep gto- | awk '{print $1}' | xargs docker rm -f || true
    docker volume ls | grep gto | awk '{print $2}' | xargs docker volume rm || true
    
    # Recreate environment
    print_status "Recreating environment..."
    docker-compose up -d postgres rabbitmq redis
    
    # Wait for services to be ready
    print_status "Waiting for infrastructure services..."
    sleep 30
    
    # Find latest backup
    local latest_backup=$(find "${BACKUP_DIR}" -name "database_*.sql.gz*" | sort | tail -1)
    
    if [[ -n "${latest_backup}" ]]; then
        print_status "Restoring from latest backup: ${latest_backup}"
        restore_database "${latest_backup}"
    else
        print_warning "No database backup found, starting with fresh database"
        docker-compose up -d
    fi
    
    print_status "Disaster recovery completed!"
}

# Show help
show_help() {
    cat << EOF
GTO Poker Solver Backup and Recovery Tool

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    backup-db              Backup database only
    backup-data            Backup application data only
    backup-config          Backup configuration only
    full-backup           Perform full backup (default)
    restore-db FILE       Restore database from backup file
    disaster-recovery     Full disaster recovery procedure
    cleanup               Clean up old backups
    health-check          Perform health check

Environment Variables:
    BACKUP_DIR            Backup directory (default: /app/backups)
    RETENTION_DAYS        Backup retention in days (default: 30)
    S3_BUCKET             S3 bucket for cloud backups
    BACKUP_ENCRYPTION_KEY Encryption key for backups

Examples:
    $0                              # Full backup
    $0 backup-db                    # Database backup only
    $0 restore-db backup.sql.gz     # Restore database
    $0 disaster-recovery            # Full disaster recovery

EOF
}

# Main execution
case "${1:-full-backup}" in
    backup-db)
        backup_database
        ;;
    backup-data)
        backup_application_data
        ;;
    backup-config)
        backup_configuration
        ;;
    full-backup)
        full_backup
        ;;
    restore-db)
        restore_database "$2"
        ;;
    point-in-time)
        point_in_time_recovery "$2"
        ;;
    disaster-recovery)
        disaster_recovery
        ;;
    cleanup)
        cleanup_old_backups
        ;;
    health-check)
        health_check
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac

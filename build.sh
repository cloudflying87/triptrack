#!/bin/bash

# Default values
BACKUP_DATA=false
BACKUP_ALL=false
REBUILD=false
SOFT_REBUILD=false
RESTORE=false
SETUP=false  # Combined migrations and static files
ALL=false
REMOTE_SERVER="davidhale87@172.16.205.4"
REMOTE_BACKUP_DIR="/halefiles/Coding/TripTrackDBBackups"

# Function to display help
show_help() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help        Show this help message"
    echo "  -d, --date DATE   Date for database filenames (required for backup/restore operations)"
    echo "  -a, --all         Run all steps"
    echo "  -b, --data        Only backup data SQL (without migrations)"
    echo "  -t, --backupall   Backup all database formats (data, full, clean)"
    echo "  -r, --rebuild     Full rebuild (all containers including DB)"
    echo "  -s, --soft        Soft rebuild (keeps DB, rebuilds other containers)"
    echo "  -o, --restore     Restore database from backup"
    echo "  -u, --setup       Run Django setup (migrations + static files)"
    echo "  --remote SERVER   Remote server address for SCP (default: $REMOTE_SERVER)"
    echo "  --remote-dir DIR  Remote directory for backups (default: $REMOTE_BACKUP_DIR)"
    echo ""
    echo "Example:"
    echo "  $0 -d 2023-05-13 -b         # Backup data with date 2023-05-13"
    echo "  $0 -a -d 2023-05-13         # Run all steps with date 2023-05-13"
    echo "  $0 -r -u                    # Full rebuild with Django setup"
    echo "  $0 -s -u                    # Soft rebuild with Django setup"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--date)
            USER_DATE="$2"
            shift 2
            ;;
        -a|--all)
            ALL=true
            shift
            ;;
        -b|--data)
            BACKUP_DATA=true
            shift
            ;;
        -t|--backupall)
            BACKUP_ALL=true
            shift
            ;;
        -r|--rebuild)
            REBUILD=true
            shift
            ;;
        -s|--soft)
            SOFT_REBUILD=true
            shift
            ;;
        -o|--restore)
            RESTORE=true
            shift
            ;;
        -u|--setup)
            SETUP=true
            shift
            ;;
        --remote)
            REMOTE_SERVER="$2"
            shift 2
            ;;
        --remote-dir)
            REMOTE_BACKUP_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# If ALL is set, enable all options
if [ "$ALL" = true ]; then
    BACKUP_ALL=true
    REBUILD=true
    RESTORE=true
    SETUP=true
fi

# Check if date is provided when needed
if [[ ("$BACKUP_DATA" = true || "$BACKUP_ALL" = true || "$RESTORE" = true) && -z "$USER_DATE" ]]; then
    echo "Error: Date (-d or --date) is required for backup/restore operations"
    show_help
    exit 1
fi

# Set default date format if needed
if [ -z "$USER_DATE" ]; then
    USER_DATE=$(date +%Y-%m-%d)
fi

# Display selected operations
echo "Running build with the following options:"
echo "Date: $USER_DATE"
echo "Backup Data Only: $BACKUP_DATA"
echo "Backup All: $BACKUP_ALL"
echo "Full Rebuild: $REBUILD"
echo "Soft Rebuild: $SOFT_REBUILD"
echo "Restore: $RESTORE"
echo "Django Setup: $SETUP"
echo "Remote Server: $REMOTE_SERVER"
echo "Remote Backup Directory: $REMOTE_BACKUP_DIR"
echo "-----------------------------------"

# Determine the Docker Compose project name
# If not explicitly set, docker compose uses the directory name
PROJECT_DIR=$(pwd)
PROJECT_NAME=$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]')

# Docker container names - these will be prefixed with the compose project name
DB_CONTAINER="${PROJECT_NAME}-triptracker_db-1"
WEB_CONTAINER="${PROJECT_NAME}-triptracker-1"
REDIS_CONTAINER="${PROJECT_NAME}-triptracker_redis-1"
TUNNEL_CONTAINER="${PROJECT_NAME}-triptracker_tunnel-1"

echo "Using project name: $PROJECT_NAME"
echo "Container names:"
echo "  DB:      $DB_CONTAINER"
echo "  Web:     $WEB_CONTAINER"
echo "  Redis:   $REDIS_CONTAINER"
echo "  Tunnel:  $TUNNEL_CONTAINER"
echo "-----------------------------------"

# Backup database (data only - no schema or migrations)
if [ "$BACKUP_DATA" = true ]; then
    echo "Taking data-only SQL backup: $USER_DATE"
    mkdir -p backups
    sudo docker exec -i $DB_CONTAINER pg_dump -U ${DB_USER:-triptracker_db_user} ${DB_NAME:-triptracker_db} -a -O -T django_migrations -f /var/lib/postgresql/data/triptracker_${USER_DATE}_data.sql 
    sudo docker cp $DB_CONTAINER:/var/lib/postgresql/data/triptracker_${USER_DATE}_data.sql ./backups/
    echo "Data backup completed: ./backups/triptracker_${USER_DATE}_data.sql"
    
    # SCP the backup to remote server
    echo "Transferring backup file to remote server"
    scp ./backups/triptracker_${USER_DATE}_data.sql $REMOTE_SERVER:$REMOTE_BACKUP_DIR/
    echo "Backup transferred to $REMOTE_SERVER:$REMOTE_BACKUP_DIR/"
fi

# Copy backup files from container to host (all formats)
if [ "$BACKUP_ALL" = true ]; then
    echo "Backing up all database formats: $USER_DATE"
    mkdir -p backups
    
    # Data only backup (no schema, no migrations)
    echo "Creating data-only backup..."
    sudo docker exec -i $DB_CONTAINER pg_dump -U ${DB_USER:-triptracker_db_user} ${DB_NAME:-triptracker_db} -a -O -T django_migrations -f /var/lib/postgresql/data/triptracker_${USER_DATE}_data.sql
    
    # Full backup (schema + data, no drop statements)
    echo "Creating full backup..."
    sudo docker exec -i $DB_CONTAINER pg_dump -U ${DB_USER:-triptracker_db_user} ${DB_NAME:-triptracker_db} -O -T django_migrations -f /var/lib/postgresql/data/triptracker_${USER_DATE}.sql
    
    # Clean backup (with drop statements for clean restore)
    echo "Creating clean backup with drop statements..."
    sudo docker exec -i $DB_CONTAINER pg_dump -U ${DB_USER:-triptracker_db_user} ${DB_NAME:-triptracker_db} -c -O -T django_migrations -f /var/lib/postgresql/data/triptracker_${USER_DATE}_clean.sql
    
    # Copy all backups to local directory
    sudo docker cp $DB_CONTAINER:/var/lib/postgresql/data/triptracker_${USER_DATE}_data.sql ./backups/
    sudo docker cp $DB_CONTAINER:/var/lib/postgresql/data/triptracker_${USER_DATE}.sql ./backups/
    sudo docker cp $DB_CONTAINER:/var/lib/postgresql/data/triptracker_${USER_DATE}_clean.sql ./backups/
    
    # SCP all backups to remote server
    echo "Transferring backup files to remote server"
    scp ./backups/triptracker_${USER_DATE}_data.sql $REMOTE_SERVER:$REMOTE_BACKUP_DIR/
    scp ./backups/triptracker_${USER_DATE}.sql $REMOTE_SERVER:$REMOTE_BACKUP_DIR/
    scp ./backups/triptracker_${USER_DATE}_clean.sql $REMOTE_SERVER:$REMOTE_BACKUP_DIR/
    
    echo "All backups completed and transferred to $REMOTE_SERVER:$REMOTE_BACKUP_DIR/"
fi

# Pull latest changes if in git repository
if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    echo "Pulling latest changes from git repository"
    git pull
fi

# Full Rebuild - rebuilds all containers including database
if [ "$REBUILD" = true ]; then
    echo "Stopping and removing all containers (including database)"
    sudo docker stop $DB_CONTAINER $WEB_CONTAINER $REDIS_CONTAINER $TUNNEL_CONTAINER 2>/dev/null || true
    sudo docker rm $DB_CONTAINER $WEB_CONTAINER $REDIS_CONTAINER $TUNNEL_CONTAINER 2>/dev/null || true
    
    echo "Pruning unused images and volumes"
    sudo docker image prune -f
    sudo docker volume prune -f
    
    echo "Starting all containers"
    sudo docker compose up -d --build
    
    # Wait for database to be ready
    echo "Waiting for database to be ready..."
    sleep 10
    
    # Check if containers are running before attempting to execute commands
    while ! sudo docker compose exec triptracker echo "Container is ready" > /dev/null 2>&1; do
        echo "Waiting for triptracker container to be ready..."
        sleep 5
    done
    
    sudo docker compose exec triptracker python manage.py collectstatic --noinput
    sudo docker compose exec triptracker python manage.py makemigrations
    sudo docker compose exec triptracker python manage.py migrate
fi

# Soft Rebuild - rebuilds all containers except database
if [ "$SOFT_REBUILD" = true ]; then
    echo "Performing soft rebuild (keeping database)"
    
    # First backup the database if date is provided
    if [ -n "$USER_DATE" ]; then
        echo "Taking precautionary database backup before soft rebuild"
        sudo docker exec -i $DB_CONTAINER pg_dump -U ${DB_USER:-triptracker_db_user} ${DB_NAME:-triptracker_db} -a -O -T django_migrations -f /var/lib/postgresql/data/triptracker_${USER_DATE}_pre_soft_rebuild.sql
        sudo docker cp $DB_CONTAINER:/var/lib/postgresql/data/triptracker_${USER_DATE}_pre_soft_rebuild.sql ./backups/
        echo "Backup saved to: ./backups/triptracker_${USER_DATE}_pre_soft_rebuild.sql"
    fi
    
    echo "Stopping and removing containers (except database)"
    sudo docker stop $WEB_CONTAINER $REDIS_CONTAINER $TUNNEL_CONTAINER 2>/dev/null || true
    sudo docker rm $WEB_CONTAINER $REDIS_CONTAINER $TUNNEL_CONTAINER 2>/dev/null || true
    
    echo "Pruning unused images (preserving database volume)"
    sudo docker image prune -f
    
    echo "Starting containers (using existing database)"
    sudo docker compose up -d triptracker triptracker_redis triptracker_tunnel --build
    
    # Wait for services to be ready
    echo "Waiting for services to be ready..."
    sleep 5
fi

# Run Django setup (migrations + static files)
if [ "$SETUP" = true ]; then
    echo "Running Django setup"
    
    echo "Applying database migrations..."
    sudo docker compose exec triptracker python manage.py makemigrations
    sudo docker compose exec triptracker python manage.py migrate
    
    echo "Collecting static files..."
    sudo docker compose exec triptracker python manage.py collectstatic --noinput
    
    echo "Django setup completed!"
fi

# Restore database
if [ "$RESTORE" = true ]; then
    echo "Restoring database from backup"
    
    # Ensure backups directory exists
    mkdir -p backups
    
    # First check if file exists locally
    if [ -f "./backups/triptracker_${USER_DATE}_data.sql" ]; then
        BACKUP_FILE="./backups/triptracker_${USER_DATE}_data.sql"
    else
        # If not found locally, try to fetch from remote server
        echo "Backup not found locally, attempting to fetch from remote server"
        scp $REMOTE_SERVER:$REMOTE_BACKUP_DIR/triptracker_${USER_DATE}_data.sql ./backups/ || {
            echo "Error: Backup file not found locally or on remote server"
            exit 1
        }
        BACKUP_FILE="./backups/triptracker_${USER_DATE}_data.sql"
    fi
    
    # Now restore from the backup file
    echo "Restoring from $BACKUP_FILE"
    sudo docker cp $BACKUP_FILE $DB_CONTAINER:/var/lib/postgresql/data/
    sudo docker exec -i $DB_CONTAINER psql -d ${DB_NAME:-triptracker_db} -U ${DB_USER:-triptracker_db_user} -f /var/lib/postgresql/data/triptracker_${USER_DATE}_data.sql
    echo "Database restored successfully!"
fi

echo "Build script completed successfully!"
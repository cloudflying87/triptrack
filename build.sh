#!/bin/bash

# Default values
BACKUP_DATA=false
BACKUP_ALL=false
REBUILD=false
RESTORE=false
MIGRATIONS=false
COLLECT_STATIC=false
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
    echo "  -r, --rebuild     Rebuild containers (stop, remove, prune)"
    echo "  -o, --restore     Restore database from backup"
    echo "  -m, --migrate     Run Django migrations"
    echo "  -s, --static      Collect static files"
    echo "  --remote SERVER   Remote server address for SCP (default: $REMOTE_SERVER)"
    echo "  --remote-dir DIR  Remote directory for backups (default: $REMOTE_BACKUP_DIR)"
    echo ""
    echo "Example:"
    echo "  $0 -d 2023-05-13 -b         # Backup data with date 2023-05-13"
    echo "  $0 -a -d 2023-05-13         # Run all steps with date 2023-05-13"
    echo "  $0 -r -m -s                 # Rebuild, run migrations and collect static"
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
        -o|--restore)
            RESTORE=true
            shift
            ;;
        -m|--migrate)
            MIGRATIONS=true
            shift
            ;;
        -s|--static)
            COLLECT_STATIC=true
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
    MIGRATIONS=true
    COLLECT_STATIC=true
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
echo "Rebuild: $REBUILD"
echo "Restore: $RESTORE"
echo "Run Migrations: $MIGRATIONS"
echo "Collect Static: $COLLECT_STATIC"
echo "Remote Server: $REMOTE_SERVER"
echo "Remote Backup Directory: $REMOTE_BACKUP_DIR"
echo "-----------------------------------"

# Docker container names - update these to match your environment
DB_CONTAINER="triptracker_db"
WEB_CONTAINER="triptracker"
REDIS_CONTAINER="triptracker_redis"
TUNNEL_CONTAINER="triptracker_tunnel"

# Backup database (data only - no schema or migrations)
if [ "$BACKUP_DATA" = true ]; then
    echo "Taking data-only SQL backup: $USER_DATE"
    mkdir -p backups
    docker exec -i $DB_CONTAINER pg_dump -U ${DB_USER:-postgres} ${DB_NAME:-triptracker} -a -O -T django_migrations -f /var/lib/postgresql/data/triptracker_${USER_DATE}_data.sql 
    docker cp $DB_CONTAINER:/var/lib/postgresql/data/triptracker_${USER_DATE}_data.sql ./backups/
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
    docker exec -i $DB_CONTAINER pg_dump -U ${DB_USER:-postgres} ${DB_NAME:-triptracker} -a -O -T django_migrations -f /var/lib/postgresql/data/triptracker_${USER_DATE}_data.sql
    
    # Full backup (schema + data, no drop statements)
    echo "Creating full backup..."
    docker exec -i $DB_CONTAINER pg_dump -U ${DB_USER:-postgres} ${DB_NAME:-triptracker} -O -T django_migrations -f /var/lib/postgresql/data/triptracker_${USER_DATE}.sql
    
    # Clean backup (with drop statements for clean restore)
    echo "Creating clean backup with drop statements..."
    docker exec -i $DB_CONTAINER pg_dump -U ${DB_USER:-postgres} ${DB_NAME:-triptracker} -c -O -T django_migrations -f /var/lib/postgresql/data/triptracker_${USER_DATE}_clean.sql
    
    # Copy all backups to local directory
    docker cp $DB_CONTAINER:/var/lib/postgresql/data/triptracker_${USER_DATE}_data.sql ./backups/
    docker cp $DB_CONTAINER:/var/lib/postgresql/data/triptracker_${USER_DATE}.sql ./backups/
    docker cp $DB_CONTAINER:/var/lib/postgresql/data/triptracker_${USER_DATE}_clean.sql ./backups/
    
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

# Rebuild containers
if [ "$REBUILD" = true ]; then
    echo "Stopping and removing containers"
    docker stop $DB_CONTAINER $WEB_CONTAINER $REDIS_CONTAINER $TUNNEL_CONTAINER 2>/dev/null || true
    docker rm $DB_CONTAINER $WEB_CONTAINER $REDIS_CONTAINER $TUNNEL_CONTAINER 2>/dev/null || true
    
    echo "Pruning unused images and volumes"
    docker image prune -f
    docker volume prune -f
    
    echo "Starting containers"
    docker-compose up -d
    
    # Wait for database to be ready
    echo "Waiting for database to be ready..."
    sleep 10
fi

# Run migrations
if [ "$MIGRATIONS" = true ]; then
    echo "Running Django migrations"
    docker-compose exec $WEB_CONTAINER python manage.py makemigrations
    docker-compose exec $WEB_CONTAINER python manage.py migrate
fi

# Collect static files
if [ "$COLLECT_STATIC" = true ]; then
    echo "Collecting static files"
    docker-compose exec $WEB_CONTAINER python manage.py collectstatic --noinput
fi

# Restore database
if [ "$RESTORE" = true ]; then
    echo "Restoring database from backup"
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
    docker cp $BACKUP_FILE $DB_CONTAINER:/var/lib/postgresql/data/
    docker exec -i $DB_CONTAINER psql -d ${DB_NAME:-triptracker} -U ${DB_USER:-postgres} -f /var/lib/postgresql/data/triptracker_${USER_DATE}_data.sql
    echo "Database restored successfully!"
fi

echo "Build script completed successfully!"
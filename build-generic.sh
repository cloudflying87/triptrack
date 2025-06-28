#!/bin/bash

# ==============================================================================
# GENERIC BUILD SCRIPT TEMPLATE
# ==============================================================================
# This is a generic build script that can be used for any Django/Docker project
# Copy this file to your project and update the PROJECT CONFIGURATION section
# ==============================================================================

# ==============================================================================
# PROJECT CONFIGURATION - UPDATE THESE FOR YOUR PROJECT
# ==============================================================================
PROJECT_NAME="myproject"                                    # Your project name (lowercase)
DB_NAME="myproject_db"                                     # Database name
DB_USER="postgres"                                         # Database user
REMOTE_SERVER="davidhale87@172.16.205.4"                  # Remote backup server
REMOTE_BACKUP_DIR="/halefiles/Coding/MyProjectDBBackups"  # Remote backup directory
LOCAL_BACKUP_DIR="/Users/davidhale87/Coding/MyProjectDBBackups"  # Local backup directory

# Container names - adjust based on your docker-compose.yml
DB_CONTAINER="${PROJECT_NAME}-db-1"
WEB_CONTAINER="${PROJECT_NAME}-web-1"
NGINX_CONTAINER="${PROJECT_NAME}-nginx-1"
# Add other containers as needed (e.g., redis, celery, etc.)
# REDIS_CONTAINER="${PROJECT_NAME}-redis-1"
# CELERY_CONTAINER="${PROJECT_NAME}-celery-1"

# ==============================================================================
# DEFAULT VALUES - DO NOT MODIFY
# ==============================================================================
BACKUP_all=false
BACKUP_data=false
BACKUP_local=false
REBUILD=false
SOFT_REBUILD=false
RESTORE=false
ALL=false
MIGRATE=false
DOWNLOAD=false

# ==============================================================================
# FUNCTIONS - DO NOT MODIFY
# ==============================================================================

# Function to display help
show_help() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help        Show this help message"
    echo "  -d, --date DATE   Date for database filenames (required for backup/restore operations)"
    echo "  -b, --backup      Backup database (all 3 formats: data, full, clean)"
    echo "  -l, --local       Local backup (all formats without Docker)"
    echo "  -r, --rebuild     Full rebuild (stop, remove, prune, migrate & restore)"
    echo "  -s, --soft        Soft rebuild (preserves database, git pull & migrate only)"
    echo "  -o, --restore     Restore database from backup"
    echo "  -m, --migrate     Run Django migrations"
    echo "  -w, --download    Download backup from remote server"
    echo ""
    echo "Example:"
    echo "  $0 -b -d 2023-05-13       # Backup with date 2023-05-13"
    echo "  $0 -l -d 2023-05-13       # Local backup with date 2023-05-13"
    echo "  $0 -r -d 2023-05-13       # Full rebuild with restore"
    echo "  $0 -s                     # Soft rebuild (no date needed)"
    echo "  $0 -w -d 2023-05-13       # Download backup from remote"
}

# Function to wait for database
wait_for_database() {
    echo "Waiting for database to be ready..."
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if sudo docker exec $DB_CONTAINER pg_isready -U $DB_USER > /dev/null 2>&1; then
            echo "Database is ready!"
            return 0
        fi
        echo "Waiting for database... (attempt $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done
    
    echo "ERROR: Database failed to become ready"
    return 1
}

# Function to create backup directory
ensure_backup_dir() {
    if [ ! -d "./backups" ]; then
        echo "Creating backup directory..."
        mkdir -p ./backups
    fi
}

# Function to ensure local backup directory exists
ensure_local_backup_dir() {
    if [ ! -d "$LOCAL_BACKUP_DIR" ]; then
        echo "Creating local backup directory..."
        mkdir -p "$LOCAL_BACKUP_DIR"
    fi
}

# Function to run Django migrations
run_migrations() {
    echo "Running Django migrations..."
    
    # Collect static files
    echo "Collecting static files..."
    sudo docker compose exec web python manage.py collectstatic --noinput --clear
    echo "✓ Static files collected"
    
    # Make migrations for all apps
    echo "Checking for new migrations..."
    sudo docker compose exec web python manage.py makemigrations
    
    # Apply all migrations
    echo "Applying database migrations..."
    sudo docker compose exec web python manage.py migrate
    echo "✓ Migrations completed"
}

# Function to backup database (all formats)
backup_database() {
    local backup_date=$1
    local is_local=$2
    
    echo "Backing up database in all formats: $backup_date"
    
    if [ "$is_local" = true ]; then
        # Local backup without Docker
        ensure_local_backup_dir
        pg_dump $DB_NAME -a -O --format=plain --file=${LOCAL_BACKUP_DIR}/${PROJECT_NAME}_backup_${backup_date}_data.sql
        pg_dump $DB_NAME -O --format=plain --file=${LOCAL_BACKUP_DIR}/${PROJECT_NAME}_backup_${backup_date}.sql
        pg_dump $DB_NAME -c -O --format=plain --file=${LOCAL_BACKUP_DIR}/${PROJECT_NAME}_backup_${backup_date}_clean.sql
        
        echo "Local backup completed"
        
        # Copy to remote if configured
        if [ -n "$REMOTE_SERVER" ]; then
            echo "Copying to remote server..."
            scp ${LOCAL_BACKUP_DIR}/${PROJECT_NAME}_backup_${backup_date}*.sql $REMOTE_SERVER:$REMOTE_BACKUP_DIR/
        fi
    else
        # Docker backup
        ensure_backup_dir
        
        # Create all three backup formats
        sudo docker exec -it $DB_CONTAINER pg_dump -U $DB_USER $DB_NAME -a -O --format=plain --file=/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}_data.sql
        sudo docker exec -it $DB_CONTAINER pg_dump -U $DB_USER $DB_NAME -O --format=plain --file=/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}.sql
        sudo docker exec -it $DB_CONTAINER pg_dump -U $DB_USER $DB_NAME -c -O --format=plain --file=/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}_clean.sql
        
        # Copy from container to host
        sudo docker cp $DB_CONTAINER:/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}_data.sql ./backups/
        sudo docker cp $DB_CONTAINER:/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}.sql ./backups/
        sudo docker cp $DB_CONTAINER:/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}_clean.sql ./backups/
        
        # Copy to remote if configured
        if [ -n "$REMOTE_SERVER" ]; then
            echo "Copying to remote server..."
            scp ./backups/${PROJECT_NAME}_backup_${backup_date}*.sql $REMOTE_SERVER:$REMOTE_BACKUP_DIR/
        fi
    fi
}

# Function to download backup from remote
download_backup() {
    local backup_date=$1
    
    echo "Downloading backup from remote server: $backup_date"
    ensure_backup_dir
    
    # Download all backup formats
    for suffix in "_data.sql" ".sql" "_clean.sql"; do
        local filename="${PROJECT_NAME}_backup_${backup_date}${suffix}"
        if scp $REMOTE_SERVER:$REMOTE_BACKUP_DIR/$filename ./backups/ 2>/dev/null; then
            echo "Downloaded: $filename"
        else
            echo "Warning: Could not download $filename"
        fi
    done
    
    # List downloaded files
    ls -la ./backups/${PROJECT_NAME}_backup_${backup_date}* 2>/dev/null || echo "No backup files found for date: $backup_date"
}

# Function to restore database
restore_database() {
    local backup_date=$1
    
    echo "Restoring database from backup: $backup_date"
    
    # Check if backup exists
    if [ ! -f "./backups/${PROJECT_NAME}_backup_${backup_date}_data.sql" ]; then
        echo "ERROR: Backup file not found: ./backups/${PROJECT_NAME}_backup_${backup_date}_data.sql"
        return 1
    fi
    
    wait_for_database || return 1
    
    # Copy backup to container
    sudo docker cp ./backups/${PROJECT_NAME}_backup_${backup_date}_data.sql $DB_CONTAINER:/var/lib/postgresql/data/
    
    # Create restore script
    echo "Creating restore script..."
    sudo docker exec -i $DB_CONTAINER bash -c 'cat > /var/lib/postgresql/data/restore.sql << '\''EOF'\''
-- Restore script
\set VERBOSITY verbose

-- Disable triggers to handle circular foreign key constraints
SET session_replication_role = replica;

-- Continue on errors during restore
\set ON_ERROR_STOP off
EOF'
    
    # Append backup content
    sudo docker exec -i $DB_CONTAINER bash -c "cat /var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}_data.sql >> /var/lib/postgresql/data/restore.sql"
    
    # Add cleanup commands
    sudo docker exec -i $DB_CONTAINER bash -c 'cat >> /var/lib/postgresql/data/restore.sql << '\''EOF'\''

-- Re-enable triggers
SET session_replication_role = DEFAULT;

\set ON_ERROR_STOP on
EOF'
    
    # Run restore
    echo "Running database restore..."
    sudo docker exec -it $DB_CONTAINER psql -d $DB_NAME -U $DB_USER -f /var/lib/postgresql/data/restore.sql
    
    echo "✓ Database restore completed successfully"
    
    # Clean up
    sudo docker exec -i $DB_CONTAINER rm -f /var/lib/postgresql/data/restore.sql
    
    echo "Database restore completed"
}

# Function to get all container names for the project
get_all_containers() {
    # List all containers that need to be managed
    # Add or remove containers based on your docker-compose.yml
    echo "$DB_CONTAINER $WEB_CONTAINER $NGINX_CONTAINER"
    # If you have more containers, add them here:
    # echo "$DB_CONTAINER $WEB_CONTAINER $NGINX_CONTAINER $REDIS_CONTAINER $CELERY_CONTAINER"
}

# Function to get non-DB containers
get_non_db_containers() {
    # List all containers except the database
    echo "$WEB_CONTAINER $NGINX_CONTAINER"
    # If you have more non-DB containers, add them here:
    # echo "$WEB_CONTAINER $NGINX_CONTAINER $REDIS_CONTAINER $CELERY_CONTAINER"
}

# Function to stop containers
stop_containers() {
    local keep_database=$1
    
    echo "Stopping containers..."
    if [ "$keep_database" = true ]; then
        echo "Keeping database container running"
        local containers=$(get_non_db_containers)
        sudo docker stop $containers 2>/dev/null || true
    else
        echo "Stopping all containers including database"
        local containers=$(get_all_containers)
        sudo docker stop $containers 2>/dev/null || true
    fi
}

# Function to remove containers
remove_containers() {
    local keep_database=$1
    
    echo "Removing containers..."
    if [ "$keep_database" = true ]; then
        echo "Keeping database container"
        local containers=$(get_non_db_containers)
        sudo docker rm $containers 2>/dev/null || true
    else
        echo "Removing all containers including database"
        local containers=$(get_all_containers)
        sudo docker rm $containers 2>/dev/null || true
    fi
}

# Function to remove volumes
remove_volumes() {
    local keep_database=$1
    
    echo "Removing volumes..."
    # Always remove these to ensure fresh files
    echo "Removing static and media volumes"
    sudo docker volume rm ${PROJECT_NAME}_static_volume 2>/dev/null || true
    sudo docker volume rm ${PROJECT_NAME}_media_volume 2>/dev/null || true
    # Add other non-DB volumes here if needed
    
    if [ "$keep_database" = true ]; then
        echo "Keeping database volume"
    else
        echo "Removing database volume"
        sudo docker volume rm ${PROJECT_NAME}_postgres_data 2>/dev/null || true
        # Add other DB-related volumes here if needed
    fi
}

# ==============================================================================
# MAIN SCRIPT
# ==============================================================================

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
        -b|--backup)
            BACKUP_all=true
            shift
            ;;
        -l|--local)
            BACKUP_local=true
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
        -m|--migrate)
            MIGRATE=true
            shift
            ;;
        -w|--download)
            DOWNLOAD=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check if date is provided when needed
if [[ ("$BACKUP_all" = true || "$BACKUP_local" = true || "$RESTORE" = true || "$DOWNLOAD" = true || "$REBUILD" = true) && -z "$USER_DATE" ]]; then
    echo "Error: Date (-d or --date) is required for this operation"
    show_help
    exit 1
fi

# Set default date if needed
if [ -z "$USER_DATE" ]; then
    USER_DATE=$(date +%Y%m%d)
fi

# Display selected operations
echo "=============================================="
echo "Project: $PROJECT_NAME"
echo "Date: $USER_DATE"
echo "=============================================="
echo "Operations:"
echo "  Backup: $BACKUP_all"
echo "  Local Backup: $BACKUP_local"
echo "  Rebuild: $REBUILD"
echo "  Soft Rebuild: $SOFT_REBUILD"
echo "  Restore: $RESTORE"
echo "  Migrate: $MIGRATE"
echo "  Download: $DOWNLOAD"
echo "=============================================="

# Execute operations

# Download backup
if [ "$DOWNLOAD" = true ]; then
    download_backup $USER_DATE
fi

# Backup operations
if [ "$BACKUP_all" = true ]; then
    backup_database $USER_DATE false
fi

if [ "$BACKUP_local" = true ]; then
    backup_database $USER_DATE true
fi

# Soft rebuild
if [ "$SOFT_REBUILD" = true ]; then
    echo "Starting soft rebuild..."
    
    # Git pull
    echo "Pulling latest changes from git..."
    git pull
    
    # Stop and remove containers (keep database running)
    stop_containers true  # keep_database=true
    remove_containers true  # keep_database=true
    
    # Remove volumes (keep database data)
    remove_volumes true  # keep_database=true
    
    # Prune and rebuild
    echo "Cleaning up unused Docker images..."
    sudo docker image prune -f
    echo "✓ Image cleanup completed"
    
    echo "Rebuilding images with --no-cache (this may take several minutes)..."
    sudo docker compose build --no-cache
    echo "✓ Images rebuilt successfully"
    
    # Start containers
    echo "Starting containers..."
    sudo docker compose up -d
    echo "✓ Containers started"
    
    # Wait and run migrations
    wait_for_database
    run_migrations
    
    echo "Soft rebuild completed!"
fi

# Full rebuild
if [ "$REBUILD" = true ]; then
    echo "Starting full rebuild..."
    
    # Git pull
    echo "Pulling latest changes from git..."
    git pull
    
    # Stop and remove everything including database
    stop_containers false  # keep_database=false (remove database)
    remove_containers false  # keep_database=false (remove database)
    remove_volumes false  # keep_database=false (remove database)
    
    # Prune and rebuild
    echo "Cleaning up unused Docker images..."
    sudo docker image prune -f
    echo "✓ Image cleanup completed"
    
    echo "Rebuilding images with --no-cache (this may take several minutes)..."
    sudo docker compose build --no-cache
    echo "✓ Images rebuilt successfully"
    
    # Start containers
    echo "Starting containers..."
    sudo docker compose up -d
    echo "✓ Containers started"
    
    # Wait and run migrations
    wait_for_database
    run_migrations
    
    # Restore database
    restore_database $USER_DATE
    
    echo "Full rebuild completed!"
fi

# Standalone restore
if [ "$RESTORE" = true ] && [ "$REBUILD" = false ]; then
    restore_database $USER_DATE
fi

# Standalone migrate
if [ "$MIGRATE" = true ] && [ "$REBUILD" = false ] && [ "$SOFT_REBUILD" = false ]; then
    run_migrations
fi

echo "=============================================="
echo "Build script completed successfully!"
echo "=============================================="
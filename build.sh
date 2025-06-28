#!/bin/bash

# Default values
BACKUP_all=false
BACKUP_data=false
BACKUP_local=false
REBUILD=false
SOFT_REBUILD=false
RESTORE=false
ALL=false
MIGRATE=false
DOWNLOAD=false
REMOTE_SERVER="davidhale87@172.16.205.4"
REMOTE_BACKUP_DIR="/halefiles/Coding/TripTrackDBBackups"

# Project specific settings
PROJECT_NAME="triptrack"
DB_CONTAINER="${PROJECT_NAME}-triptracker_db-1"
WEB_CONTAINER="${PROJECT_NAME}-triptracker-1"
REDIS_CONTAINER="${PROJECT_NAME}-triptracker_redis-1"
TUNNEL_CONTAINER="${PROJECT_NAME}-triptracker_tunnel-1"
DB_NAME="triptracker_db"
DB_USER="triptracker_db_user"

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

# Function to run Django migrations
run_migrations() {
    echo "Running Django migrations..."
    
    # Collect static files
    echo "Collecting static files..."
    sudo docker compose exec triptracker python manage.py collectstatic --noinput --clear
    echo "✓ Static files collected"
    
    # Make migrations for all apps
    echo "Checking for new migrations..."
    sudo docker compose exec triptracker python manage.py makemigrations
    
    # Apply all migrations
    echo "Applying database migrations..."
    sudo docker compose exec triptracker python manage.py migrate
    echo "✓ Migrations completed"
}

# Function to backup database (all formats)
backup_database() {
    local backup_date=$1
    local is_local=$2
    
    echo "Backing up database in all formats: $backup_date"
    
    if [ "$is_local" = true ]; then
        # Local backup without Docker
        LOCAL_BACKUP_DIR="/Users/davidhale87/Coding/TripTrackDBBackups"
        mkdir -p "$LOCAL_BACKUP_DIR"
        
        pg_dump $DB_NAME -a -O --format=plain --file=${LOCAL_BACKUP_DIR}/${PROJECT_NAME}_backup_${backup_date}_data.sql
        pg_dump $DB_NAME -O --format=plain --file=${LOCAL_BACKUP_DIR}/${PROJECT_NAME}_backup_${backup_date}.sql
        pg_dump $DB_NAME -c -O --format=plain --file=${LOCAL_BACKUP_DIR}/${PROJECT_NAME}_backup_${backup_date}_clean.sql
        
        # Check file sizes and remove files smaller than 1MB
        min_size=1048576
        valid_backups=()
        
        for suffix in "_data.sql" ".sql" "_clean.sql"; do
            filename="${LOCAL_BACKUP_DIR}/${PROJECT_NAME}_backup_${backup_date}${suffix}"
            
            if [ -f "$filename" ]; then
                file_size=$(stat -c%s "$filename" 2>/dev/null || echo "0")
                
                if [ "$file_size" -gt "$min_size" ]; then
                    echo "✓ Valid backup: $(basename "$filename") (${file_size} bytes)"
                    valid_backups+=("$filename")
                else
                    echo "⚠ Removing small backup: $(basename "$filename") (${file_size} bytes, minimum: ${min_size})"
                    rm -f "$filename"
                fi
            fi
        done
        
        echo "Local backup completed - ${#valid_backups[@]} valid files"
        
        # Copy to remote if configured
        if [ -n "$REMOTE_SERVER" ] && [ ${#valid_backups[@]} -gt 0 ]; then
            echo "Copying valid backups to remote server..."
            for backup_file in "${valid_backups[@]}"; do
                echo "  Uploading $(basename "$backup_file")"
                scp "$backup_file" $REMOTE_SERVER:$REMOTE_BACKUP_DIR/
            done
        fi
    else
        # Docker backup
        ensure_backup_dir
        
        # Create all three backup formats
        sudo docker exec -it $DB_CONTAINER pg_dump -U $DB_USER $DB_NAME -a -O --format=plain --file=/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}_data.sql
        sudo docker exec -it $DB_CONTAINER pg_dump -U $DB_USER $DB_NAME -O --format=plain --file=/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}.sql
        sudo docker exec -it $DB_CONTAINER pg_dump -U $DB_USER $DB_NAME -c -O --format=plain --file=/var/lib/postgresql/data/${PROJECT_NAME}_backup_${backup_date}_clean.sql
        
        # Check file sizes and only copy files larger than 1MB (1048576 bytes)
        min_size=1048576
        
        for suffix in "_data.sql" ".sql" "_clean.sql"; do
            filename="${PROJECT_NAME}_backup_${backup_date}${suffix}"
            
            # Get file size from within container
            file_size=$(sudo docker exec $DB_CONTAINER stat -c%s /var/lib/postgresql/data/$filename 2>/dev/null || echo "0")
            
            if [ "$file_size" -gt "$min_size" ]; then
                echo "✓ Copying $filename (${file_size} bytes)"
                sudo docker cp $DB_CONTAINER:/var/lib/postgresql/data/$filename ./backups/
            else
                echo "⚠ Skipping $filename - too small (${file_size} bytes, minimum: ${min_size})"
                # Clean up small backup file from container
                sudo docker exec $DB_CONTAINER rm -f /var/lib/postgresql/data/$filename
            fi
        done
        
        # Copy to remote if configured
        if [ -n "$REMOTE_SERVER" ]; then
            echo "Copying valid backups to remote server..."
            # Only copy files that exist in the backups directory
            for backup_file in ./backups/${PROJECT_NAME}_backup_${backup_date}*.sql; do
                if [ -f "$backup_file" ]; then
                    echo "  Uploading $(basename "$backup_file")"
                    scp "$backup_file" $REMOTE_SERVER:$REMOTE_BACKUP_DIR/
                fi
            done
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

# Function to stop containers
stop_containers() {
    local keep_database=$1
    
    echo "Stopping containers..."
    if [ "$keep_database" = true ]; then
        echo "Keeping database container running"
        sudo docker stop $WEB_CONTAINER $REDIS_CONTAINER $TUNNEL_CONTAINER 2>/dev/null || true
    else
        echo "Stopping all containers including database"
        sudo docker stop $DB_CONTAINER $WEB_CONTAINER $REDIS_CONTAINER $TUNNEL_CONTAINER 2>/dev/null || true
    fi
}

# Function to remove containers
remove_containers() {
    local keep_database=$1
    
    echo "Removing containers..."
    if [ "$keep_database" = true ]; then
        echo "Keeping database container"
        sudo docker rm $WEB_CONTAINER $REDIS_CONTAINER $TUNNEL_CONTAINER 2>/dev/null || true
    else
        echo "Removing all containers including database"
        sudo docker rm $DB_CONTAINER $WEB_CONTAINER $REDIS_CONTAINER $TUNNEL_CONTAINER 2>/dev/null || true
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
    
    if [ "$keep_database" = true ]; then
        echo "Keeping database volume"
    else
        echo "Removing database volume"
        sudo docker volume rm ${PROJECT_NAME}_postgres_data 2>/dev/null || true
    fi
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
echo "Running build with the following options:"
echo "Date: $USER_DATE"
echo "Backup: $BACKUP_all"
echo "Local Backup: $BACKUP_local"
echo "Rebuild: $REBUILD"
echo "Soft Rebuild: $SOFT_REBUILD"
echo "Restore: $RESTORE"
echo "Migrate: $MIGRATE"
echo "Download: $DOWNLOAD"
echo "-----------------------------------"

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

echo "Build script completed successfully!"
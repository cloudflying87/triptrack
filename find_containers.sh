#!/bin/bash

# Script to find the correct container names for the Docker Compose project

echo "Finding Docker container names for this project..."
echo "Current directory: $(pwd)"
echo ""

# Get the project name from docker compose
PROJECT_NAME=$(sudo docker compose ps --format json | jq -r '.[0].Project' 2>/dev/null)

if [ -z "$PROJECT_NAME" ]; then
    echo "No containers found. Trying to determine project name from directory..."
    # Default project name is the directory name
    PROJECT_NAME=$(basename "$(pwd)")
    echo "Project name would be: $PROJECT_NAME"
else
    echo "Docker Compose project name: $PROJECT_NAME"
fi

echo ""
echo "Container names would be:"
echo "  Web:     ${PROJECT_NAME}-triptracker-1"
echo "  DB:      ${PROJECT_NAME}-triptracker_db-1"
echo "  Redis:   ${PROJECT_NAME}-triptracker_redis-1"
echo "  Tunnel:  ${PROJECT_NAME}-triptracker_tunnel-1"

echo ""
echo "Current running containers:"
sudo docker ps --format "table {{.Names}}\t{{.Status}}"
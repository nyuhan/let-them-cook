#!/bin/sh
set -e

if [ -z "$GOOGLE_MAPS_API_KEY" ]; then
    echo "Error: GOOGLE_MAPS_API_KEY environment variable is not set."
    exit 1
fi

# Ensure /data is mounted (directory must exist, created by Docker volume mount)
if [ ! -d "/data" ]; then
    echo "Error: /data directory not found. Please mount a volume to /data."
    echo "       example: -v \$(pwd)/data:/data"
    exit 1
fi

# Execute the CMD passed to docker run (defaults to "python app.py" via Dockerfile)
exec "$@"

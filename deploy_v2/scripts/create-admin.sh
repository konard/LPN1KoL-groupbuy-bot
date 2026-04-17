#!/bin/sh
# Create an admin user inside the running backend container.
# Usage: ./scripts/create-admin.sh <username> <email> <password>
set -e

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <username> <email> <password>"
    exit 1
fi

docker compose exec backend python create_admin.py "$1" "$2" "$3"

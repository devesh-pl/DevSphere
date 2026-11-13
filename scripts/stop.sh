#!/usr/bin/env bash

set -Eeuo pipefail

cd "$(dirname "$0")/.."

docker compose \
    --env-file .env \
    -f infrastructure/docker/docker-compose.yml \
    down

echo "Containers stopped. Persistent data retained."

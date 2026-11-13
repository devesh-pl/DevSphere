#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

docker compose \
    --env-file "$ROOT_DIR/.env" \
    -f "$ROOT_DIR/infrastructure/docker/docker-compose.yml" \
    -f "$ROOT_DIR/infrastructure/docker/docker-compose.dev.yml" \
    down

echo ""
echo "DevSphere development containers stopped."
echo "Persistent volumes retained."

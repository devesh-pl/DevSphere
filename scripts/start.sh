#!/usr/bin/env bash

set -Eeuo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
    echo "ERROR: .env missing. Run bash scripts/setup.sh first."
    exit 1
fi

docker compose \
    --env-file .env \
    -f infrastructure/docker/docker-compose.yml \
    up -d --remove-orphans

echo ""
echo "DevSphere infrastructure started."

docker compose \
    --env-file .env \
    -f infrastructure/docker/docker-compose.yml \
    ps

#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
    echo "ERROR: .env file missing."
    echo "Run bash scripts/setup.sh first."
    exit 1
fi

COMPOSE=(
    docker compose
    --env-file "$ROOT_DIR/.env"
    -f "$ROOT_DIR/infrastructure/docker/docker-compose.yml"
    -f "$ROOT_DIR/infrastructure/docker/docker-compose.dev.yml"
)

echo "Validating development configuration..."

"${COMPOSE[@]}" config --quiet

echo ""
echo "Starting DevSphere development environment..."

"${COMPOSE[@]}" up -d --build --remove-orphans

echo ""
echo "========== DEVSPHERE CONTAINERS =========="

"${COMPOSE[@]}" ps

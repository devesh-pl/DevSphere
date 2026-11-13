#!/usr/bin/env bash

set -Eeuo pipefail

cd "$(dirname "$0")/.."

for tool in docker openssl; do
    command -v "$tool" >/dev/null || {
        echo "ERROR: $tool is not installed."
        exit 1
    }
done

if [[ ! -f .env.example ]]; then
    echo "ERROR: Root .env.example is missing."
    exit 1
fi

required_variables=(
    POSTGRES_USER
    POSTGRES_PASSWORD
    POSTGRES_DB
    AUTH_DB_PASSWORD
    CATALOG_DB_PASSWORD
    ORCHESTRATOR_DB_PASSWORD
    BUILD_DB_PASSWORD
    DEPLOYMENT_DB_PASSWORD
    CONFIGURATION_DB_PASSWORD
    RABBITMQ_DEFAULT_USER
    RABBITMQ_DEFAULT_PASS
)

for variable in "${required_variables[@]}"; do
    if ! grep -q "^${variable}=" .env.example; then
        echo "ERROR: Missing $variable in .env.example"
        exit 1
    fi
done

if [[ ! -f .env ]]; then
    cp .env.example .env

    while IFS='=' read -r key value; do
        case "$key" in
            *_PASSWORD|*_PASS)
                secret="$(openssl rand -hex 32)"
                sed -i '' "s/^${key}=.*/${key}=${secret}/" .env
                ;;
        esac
    done < .env.example

    chmod 600 .env
    echo "Generated unique local credentials."
else
    echo "Existing .env preserved."
fi

docker info >/dev/null 2>&1 || {
    echo "ERROR: Docker Engine is not running."
    exit 1
}

docker compose \
    --env-file .env \
    -f infrastructure/docker/docker-compose.yml \
    config --quiet

echo "DevSphere setup completed successfully."

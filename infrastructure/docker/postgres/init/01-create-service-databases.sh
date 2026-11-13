#!/usr/bin/env bash

set -Eeuo pipefail

create_service_database() {
    local role_name="$1"
    local database_name="$2"
    local password_variable="$3"

    local role_password="${!password_variable:-}"

    if [[ -z "$role_password" ]]; then
        echo "ERROR: Missing $password_variable"
        exit 1
    fi

    echo "Initializing $database_name"

    psql \
        --no-psqlrc \
        --set=ON_ERROR_STOP=1 \
        --username "$POSTGRES_USER" \
        --dbname "$POSTGRES_DB" \
        --set=role_name="$role_name" \
        --set=role_password="$role_password" \
        --set=database_name="$database_name" <<'SQL'

SELECT format(
    'CREATE ROLE %I LOGIN PASSWORD %L',
    :'role_name',
    :'role_password'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = :'role_name'
)
\gexec

SELECT format(
    'CREATE DATABASE %I OWNER %I',
    :'database_name',
    :'role_name'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = :'database_name'
)
\gexec

SQL

    echo "Created $database_name"
}

create_service_database auth_service auth_db AUTH_DB_PASSWORD
create_service_database catalog_service catalog_db CATALOG_DB_PASSWORD
create_service_database orchestrator_service orchestrator_db ORCHESTRATOR_DB_PASSWORD
create_service_database build_service build_db BUILD_DB_PASSWORD
create_service_database deployment_service deployment_db DEPLOYMENT_DB_PASSWORD
create_service_database configuration_service configuration_db CONFIGURATION_DB_PASSWORD

echo "DevSphere database initialization completed."

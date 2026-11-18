"""Add project_db and safe Build CRUD columns without resetting existing databases."""
from pathlib import Path
import os
import secrets
import subprocess
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
local = ROOT / '.env.spring.local'
values = dotenv_values(local) if local.exists() else {}
password = values.get('PROJECT_DB_PASSWORD')


def psql(sql, database='postgres', role=None):
    command = ['docker', 'exec', '-i', 'devsphere-postgres', 'sh', '-c',
               'exec psql --no-psqlrc -v ON_ERROR_STOP=1 -U "${1:-$POSTGRES_USER}" -d "$2"',
               'sh', role or '', database]
    result = subprocess.run(command, input=sql, text=True, capture_output=True)
    if result.returncode:
        # Do not echo SQL or connection arguments, which may contain credentials.
        raise SystemExit(f'Database preparation failed for {database}; inspect PostgreSQL locally.')
    return result.stdout


exists = '1' in psql("SELECT 1 FROM pg_roles WHERE rolname='project_service';").split()
if exists and not password:
    raise SystemExit('project_service exists. Set its matching PROJECT_DB_PASSWORD in .env.spring.local; existing credentials will not be rotated.')
if not password:
    password = secrets.token_urlsafe(32)
    fd = os.open(local, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as file:
        file.write(f'PROJECT_DB_PASSWORD={password}\nJAVA_DEPLOYMENT_WRITES=false\nLOCAL_UID={os.getuid()}\nLOCAL_GID={os.getgid()}\n')
# SQL quote rather than shell interpolation; never print this statement.
literal = "'" + password.replace("'", "''") + "'"
if not exists:
    psql(f'CREATE ROLE project_service LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {literal};')
psql("SELECT 'CREATE DATABASE project_db OWNER project_service' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='project_db')\\gexec\n")
psql((ROOT / 'services/build-service/migrations/004_safe_crud.sql').read_text(), 'build_db')
print('PASS: project_db prepared; additive Build CRUD migration applied. Existing data retained.')

# DevSphere Authentication Service

## Purpose

Provides the authentication foundation for DevSphere.

The authentication business logic will be implemented in Phase 3.

## Technology

- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL
- Psycopg
- Alembic
- Pytest

## API

GET /health
GET /ready

## Local execution

Activate the repository virtual environment.

Run:

uvicorn app.main:app --reload --port 8001

## Testing

pytest -q

## Database

Database: auth_db

Owner: auth_service

Migrations: Alembic
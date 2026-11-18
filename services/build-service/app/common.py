"""Shared configuration and database access for DevSphere builds."""

import importlib.util
import os
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[3]

load_dotenv(ROOT / ".env.build.local")

DATABASE_URL = os.environ["BUILD_DATABASE_URL"]
TOKEN_KEY = os.environ["BUILD_TOKEN_KEY"]

cipher = Fernet(TOKEN_KEY.encode())

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=3,
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

AUTH = os.getenv("AUTH_SERVICE_URL", "http://127.0.0.1:8001")
ORCH = os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8004")
DEPLOY = os.getenv("DEPLOYMENT_URL", "http://127.0.0.1:8005")

runner_path = ROOT / "scripts/build-and-deploy.py"
spec = importlib.util.spec_from_file_location(
    "devsphere_build_runner",
    runner_path,
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def utc_now():
    return datetime.now(timezone.utc)


def row_to_dict(row):
    if row is None:
        return None

    item = dict(row)

    # Never expose stored credentials or internal leases.
    item.pop("token_ciphertext", None)
    item.pop("lease_owner", None)

    item["error"] = item.get("error_message")

    for field in (
        "created_at",
        "updated_at",
        "lease_expires_at",
        "last_heartbeat_at",
        "archived_at",
    ):
        if item.get(field):
            item[field] = item[field].isoformat()

    return item


def get_job(job_id):
    with SessionLocal() as db:
        row = db.execute(
            text("SELECT * FROM build_jobs WHERE id=:id"),
            {"id": job_id},
        ).mappings().first()

        return row_to_dict(row)

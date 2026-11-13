from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


@lru_cache(maxsize=1)
def _create_engine(database_url: str) -> Engine:

    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=1,
        pool_timeout=5,
    )


def get_engine() -> Engine:

    if not settings.database_url:

        raise RuntimeError(
            "DATABASE_URL has not been configured"
        )

    return _create_engine(settings.database_url)


def check_database_connection() -> bool:

    engine = get_engine()

    with engine.connect() as connection:

        connection.execute(text("SELECT 1"))

    return True


def get_db() -> Generator[Session, None, None]:

    SessionLocal = sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
    )

    with SessionLocal() as session:

        yield session
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=1,
        pool_timeout=5,
    )


def get_db():
    session_factory = sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
    )

    with session_factory() as session:
        yield session


def check_database_connection():
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))

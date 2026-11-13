from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CatalogService(Base):
    __tablename__ = "catalog_services"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )

    repository_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )

    language: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    framework: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    owner_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
        nullable=False,
    )


    provisioning_operation_id: Mapped[str | None] = mapped_column(
        String(36),
        unique=True,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

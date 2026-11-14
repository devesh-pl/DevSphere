"""Create the transactional operation outbox."""

from alembic import op
import sqlalchemy as sa

revision = "ddea8e050a5a"
down_revision = "62a5863dab62"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "operation_outbox",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
        ),
        sa.Column(
            "operation_id",
            sa.String(36),
            sa.ForeignKey("operations.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "event_type",
            sa.String(100),
            nullable=False,
        ),
        sa.Column(
            "payload",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_operation_outbox_dispatch",
        "operation_outbox",
        [
            "status",
            "next_attempt_at",
        ],
    )


def downgrade():
    op.drop_index(
        "ix_operation_outbox_dispatch",
        table_name="operation_outbox",
    )
    op.drop_table("operation_outbox")

"""Add worker leases and recovery metadata."""

from alembic import op
import sqlalchemy as sa

revision = "60ddeff18caa"
down_revision = "ddea8e050a5a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "operations",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "operations",
        sa.Column(
            "lease_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "operations",
        sa.Column(
            "last_heartbeat_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_operations_lease_recovery",
        "operations",
        ["status", "lease_expires_at"],
    )


def downgrade():
    op.drop_index(
        "ix_operations_lease_recovery",
        table_name="operations",
    )

    op.drop_column("operations", "last_heartbeat_at")
    op.drop_column("operations", "lease_expires_at")
    op.drop_column("operations", "attempt_count")

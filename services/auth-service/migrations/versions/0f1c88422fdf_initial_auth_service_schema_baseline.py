"""initial auth service schema baseline

Revision ID: 0f1c88422fdf
Revises: 
Create Date: 2026-11-14 00:15:59.955692

"""

from typing import Sequence, Union

from alembic import op

import sqlalchemy as sa


revision: str = '0f1c88422fdf'

down_revision: Union[str, Sequence[str], None] = None

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    pass


def downgrade() -> None:

    pass
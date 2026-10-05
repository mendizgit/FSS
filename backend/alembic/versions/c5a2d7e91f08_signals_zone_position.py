"""signals: bring back zone_position

Revision ID: c5a2d7e91f08
Revises: b3e8f01c6d44
Create Date: 2026-10-06 01:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5a2d7e91f08"
down_revision: str | Sequence[str] | None = "b3e8f01c6d44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema (filled by the next signal run)."""
    op.add_column("signals", sa.Column("zone_position", sa.String(length=16), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("signals", "zone_position")

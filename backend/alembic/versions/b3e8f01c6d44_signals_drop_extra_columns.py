"""signals: drop columns the dashboard no longer shows

Revision ID: b3e8f01c6d44
Revises: 7a1d3c9e5b20
Create Date: 2026-10-06 00:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3e8f01c6d44"
down_revision: str | Sequence[str] | None = "7a1d3c9e5b20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DROPPED = (
    "htf_supertrend",
    "local_supertrend",
    "consolidated_trend",
    "long_score",
    "short_score",
    "long_grade",
    "short_grade",
    "rsi_divergence",
    "sr_letter",
    "zone_position",
)


def upgrade() -> None:
    """Upgrade schema (derived values only; signals are recomputed every run)."""
    for name in DROPPED:
        op.drop_column("signals", name)


def downgrade() -> None:
    """Downgrade schema: columns come back empty (nullable) and refill on the next run."""
    op.add_column("signals", sa.Column("zone_position", sa.String(length=16), nullable=True))
    op.add_column("signals", sa.Column("sr_letter", sa.String(length=1), nullable=True))
    op.add_column("signals", sa.Column("rsi_divergence", sa.String(length=8), nullable=True))
    op.add_column("signals", sa.Column("short_grade", sa.String(length=1), nullable=True))
    op.add_column("signals", sa.Column("long_grade", sa.String(length=1), nullable=True))
    op.add_column("signals", sa.Column("short_score", sa.Integer(), nullable=True))
    op.add_column("signals", sa.Column("long_score", sa.Integer(), nullable=True))
    op.add_column("signals", sa.Column("consolidated_trend", sa.String(length=16), nullable=True))
    op.add_column("signals", sa.Column("local_supertrend", sa.String(length=8), nullable=True))
    op.add_column("signals", sa.Column("htf_supertrend", sa.String(length=8), nullable=True))

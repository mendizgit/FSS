"""signal_setups: latest Long / Short setup per symbol, for exactly-once Telegram alerts

Revision ID: d8f3a6b2c914
Revises: c5a2d7e91f08
Create Date: 2026-10-07 00:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8f3a6b2c914"
down_revision: str | Sequence[str] | None = "c5a2d7e91f08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signal_setups",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("bias", sa.String(length=5), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("trigger_timeframe", sa.String(length=4), nullable=False),
        sa.Column("trigger_event", sa.String(length=8), nullable=False),
        sa.Column("trigger_bar_close_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("against_htf", sa.Boolean(), nullable=True),
        sa.Column("htf_event", sa.String(length=8), nullable=False),
        sa.Column("htf_bars_ago", sa.Integer(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("bias IN ('long', 'short')", name=op.f("ck_signal_setups_bias")),
        sa.PrimaryKeyConstraint("symbol", name=op.f("pk_signal_setups")),
    )


def downgrade() -> None:
    op.drop_table("signal_setups")

"""entry signal (Pine v3): score columns on signals, entry fields + alert cooldown on signal_setups

Revision ID: e4b9c7d2a135
Revises: d8f3a6b2c914
Create Date: 2026-10-27 12:00:00.000000

Non-destructive: only adds nullable columns and relaxes three legacy NOT NULL columns. Existing
signal_setups rows (event-based rule) are marked inactive so the entry rule starts clean.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4b9c7d2a135"
down_revision: str | Sequence[str] | None = "d8f3a6b2c914"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name, kind in (
        ("htf_dir", sa.SmallInteger()),
        ("long_score", sa.SmallInteger()),
        ("short_score", sa.SmallInteger()),
        ("long_factors", sa.String(length=24)),
        ("short_factors", sa.String(length=24)),
        ("entry_long", sa.Boolean()),
        ("entry_short", sa.Boolean()),
        ("stoch_dir", sa.SmallInteger()),
    ):
        op.add_column("signals", sa.Column(name, kind, nullable=True))
    op.alter_column("signal_setups", "trigger_event", existing_type=sa.String(8), nullable=True)
    op.alter_column("signal_setups", "htf_event", existing_type=sa.String(8), nullable=True)
    op.alter_column("signal_setups", "htf_bars_ago", existing_type=sa.Integer(), nullable=True)
    op.add_column("signal_setups", sa.Column("score", sa.SmallInteger(), nullable=True))
    op.add_column("signal_setups", sa.Column("factors", sa.String(length=24), nullable=True))
    op.add_column(
        "signal_setups",
        sa.Column("last_long_alert_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "signal_setups",
        sa.Column("last_short_alert_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE signal_setups SET active = false")


def downgrade() -> None:
    op.drop_column("signal_setups", "last_short_alert_at")
    op.drop_column("signal_setups", "last_long_alert_at")
    op.drop_column("signal_setups", "factors")
    op.drop_column("signal_setups", "score")
    for name in (
        "stoch_dir",
        "entry_short",
        "entry_long",
        "short_factors",
        "long_factors",
        "short_score",
        "long_score",
        "htf_dir",
    ):
        op.drop_column("signals", name)

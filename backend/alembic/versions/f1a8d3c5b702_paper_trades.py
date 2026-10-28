"""paper_trades: dummy-money trades for the 15m entry alerts

Revision ID: f1a8d3c5b702
Revises: e4b9c7d2a135
Create Date: 2026-10-28 01:00:00.000000

Non-destructive: only creates a new table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a8d3c5b702"
down_revision: str | Sequence[str] | None = "e4b9c7d2a135"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_trades",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=5), nullable=False),
        sa.Column("status", sa.String(length=6), nullable=False),
        sa.Column("setup_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_price", sa.Float(), nullable=False),
        sa.Column("target_price", sa.Float(), nullable=False),
        sa.Column("margin_usdt", sa.Float(), nullable=False),
        sa.Column("notional_usdt", sa.Float(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=True),
        sa.Column("factors", sa.String(length=24), nullable=True),
        sa.Column("against_htf", sa.Boolean(), nullable=True),
        sa.Column("flip_events", sa.String(length=48), nullable=True),
        sa.Column("flip_confirms", sa.Boolean(), nullable=False),
        sa.Column("mfe_pct", sa.Float(), nullable=True),
        sa.Column("mae_pct", sa.Float(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("exit_reason", sa.String(length=12), nullable=True),
        sa.Column("fees_usdt", sa.Float(), nullable=True),
        sa.Column("pnl_usdt", sa.Float(), nullable=True),
        sa.Column("r_multiple", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("side IN ('long', 'short')", name="ck_paper_trades_side"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_paper_trades_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "side", "setup_detected_at", name="uq_paper_trade_setup"),
    )
    op.create_index("ix_paper_trades_status", "paper_trades", ["status"])


def downgrade() -> None:
    op.drop_index("ix_paper_trades_status", table_name="paper_trades")
    op.drop_table("paper_trades")

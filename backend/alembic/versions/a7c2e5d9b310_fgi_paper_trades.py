"""fgi_paper_trades: dummy-money trades of the FGI Pro strategy

Revision ID: a7c2e5d9b310
Revises: f1a8d3c5b702
Create Date: 2026-10-29 06:00:00.000000

Non-destructive: only creates a new table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c2e5d9b310"
down_revision: str | Sequence[str] | None = "f1a8d3c5b702"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fgi_paper_trades",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=5), nullable=False),
        sa.Column("status", sa.String(length=6), nullable=False),
        sa.Column("signal_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_price", sa.Float(), nullable=False),
        sa.Column("stop0_price", sa.Float(), nullable=False),
        sa.Column("tp1_price", sa.Float(), nullable=False),
        sa.Column("tp2_price", sa.Float(), nullable=False),
        sa.Column("atr", sa.Float(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("margin_usdt", sa.Float(), nullable=False),
        sa.Column("notional_usdt", sa.Float(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("adx", sa.Float(), nullable=False),
        sa.Column("remaining_frac", sa.Float(), nullable=False),
        sa.Column("tp1_done", sa.Boolean(), nullable=False),
        sa.Column("be", sa.Boolean(), nullable=False),
        sa.Column("flip_pending", sa.Boolean(), nullable=False),
        sa.Column("gross_usdt", sa.Float(), nullable=False),
        sa.Column("fees_usdt", sa.Float(), nullable=False),
        sa.Column("scanned_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mfe_pct", sa.Float(), nullable=True),
        sa.Column("mae_pct", sa.Float(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("exit_reason", sa.String(length=8), nullable=True),
        sa.Column("pnl_usdt", sa.Float(), nullable=True),
        sa.Column("r_multiple", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("side IN ('long', 'short')", name="ck_fgi_paper_trades_side"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_fgi_paper_trades_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "side", "signal_at", name="uq_fgi_paper_trade_signal"),
    )
    op.create_index("ix_fgi_paper_trades_status", "fgi_paper_trades", ["status"])


def downgrade() -> None:
    op.drop_index("ix_fgi_paper_trades_status", table_name="fgi_paper_trades")
    op.drop_table("fgi_paper_trades")

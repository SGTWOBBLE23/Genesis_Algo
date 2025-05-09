"""create trade_logs table

Revision ID: 20250508_trade_logs
Revises: <previous_rev>
Create Date: 2025-05-08 13:15:00 HST
"""
from alembic import op
import sqlalchemy as sa

revision = '20250508_trade_logs'
down_revision = 'c0ff33b07da1'        # ← replace with the *current head* ID
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'trade_logs',
        sa.Column('id',            sa.String(), primary_key=True),
        sa.Column('timestamp',     sa.DateTime(), nullable=False),
        sa.Column('symbol',        sa.String(20), nullable=False),
        sa.Column('timeframe',     sa.String(10)),
        sa.Column('action',        sa.String(20)),
        sa.Column('entry',         sa.Float()),
        sa.Column('sl',            sa.Float()),
        sa.Column('tp',            sa.Float()),
        sa.Column('confidence',    sa.Float()),
        sa.Column('result',        sa.String(10)),
        sa.Column('exit_price',    sa.Float()),
        sa.Column('exit_time',     sa.DateTime()),
        sa.Column('duration_sec',  sa.Integer()),
        sa.Column('max_drawdown',  sa.Float()),
        sa.Column('max_favorable', sa.Float()),
        sa.Column('chart_id',      sa.String(200)),
    )


def downgrade() -> None:
    op.drop_table('trade_logs')

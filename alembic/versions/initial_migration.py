"""Initial migration

Revision ID: c0ff33b07da1
Revises: 
Create Date: 2023-07-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c0ff33b07da1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_pw', sa.String(length=255), nullable=False),
        sa.Column('role', sa.Enum('ADMIN', 'USER', 'VIEWER', name='role'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    
    # Create settings table
    op.create_table('settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('section', sa.String(length=50), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create signals table
    op.create_table('signals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('action', sa.Enum('ANTICIPATED_LONG', 'ANTICIPATED_SHORT', 'BUY_NOW', 'SELL_NOW', name='signalaction'), nullable=False),
        sa.Column('entry', sa.Float(), nullable=True),
        sa.Column('sl', sa.Float(), nullable=True),
        sa.Column('tp', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'ACTIVE', 'TRIGGERED', 'EXPIRED', 'CANCELLED', name='signalstatus'), nullable=True),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create trades table
    op.create_table('trades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('signal_id', sa.Integer(), nullable=True),
        sa.Column('ticket', sa.String(length=50), nullable=True),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('side', sa.Enum('BUY', 'SELL', name='tradeside'), nullable=False),
        sa.Column('lot', sa.Float(), nullable=False),
        sa.Column('entry', sa.Float(), nullable=True),
        sa.Column('exit', sa.Float(), nullable=True),
        sa.Column('sl', sa.Float(), nullable=True),
        sa.Column('tp', sa.Float(), nullable=True),
        sa.Column('pnl', sa.Float(), nullable=True),
        sa.Column('status', sa.Enum('OPEN', 'CLOSED', 'CANCELLED', 'PARTIALLY_CLOSED', name='tradestatus'), nullable=True),
        sa.Column('opened_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['signal_id'], ['signals.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create risk_profiles table
    op.create_table('risk_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('json_rules', sa.JSON(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create logs table
    op.create_table('logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ts', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('level', sa.Enum('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', name='loglevel'), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indices
    op.create_index(op.f('ix_signals_symbol'), 'signals', ['symbol'], unique=False)
    op.create_index(op.f('ix_signals_created_at'), 'signals', ['created_at'], unique=False)
    
    op.create_index(op.f('ix_trades_symbol'), 'trades', ['symbol'], unique=False)
    op.create_index(op.f('ix_trades_opened_at'), 'trades', ['opened_at'], unique=False)
    
    op.create_index(op.f('ix_logs_ts'), 'logs', ['ts'], unique=False)
    op.create_index(op.f('ix_logs_level'), 'logs', ['level'], unique=False)
    op.create_index(op.f('ix_logs_source'), 'logs', ['source'], unique=False)
    
    op.create_index(op.f('ix_settings_section'), 'settings', ['section'], unique=False)


def downgrade() -> None:
    # Drop indices
    op.drop_index(op.f('ix_settings_section'), table_name='settings')
    
    op.drop_index(op.f('ix_logs_source'), table_name='logs')
    op.drop_index(op.f('ix_logs_level'), table_name='logs')
    op.drop_index(op.f('ix_logs_ts'), table_name='logs')
    
    op.drop_index(op.f('ix_trades_opened_at'), table_name='trades')
    op.drop_index(op.f('ix_trades_symbol'), table_name='trades')
    
    op.drop_index(op.f('ix_signals_created_at'), table_name='signals')
    op.drop_index(op.f('ix_signals_symbol'), table_name='signals')
    
    # Drop tables
    op.drop_table('logs')
    op.drop_table('risk_profiles')
    op.drop_table('trades')
    op.drop_table('signals')
    op.drop_table('settings')
    op.drop_table('users')
    
    # Drop enums
    op.execute("DROP TYPE loglevel")
    op.execute("DROP TYPE tradestatus")
    op.execute("DROP TYPE tradeside")
    op.execute("DROP TYPE signalstatus")
    op.execute("DROP TYPE signalaction")
    op.execute("DROP TYPE role")

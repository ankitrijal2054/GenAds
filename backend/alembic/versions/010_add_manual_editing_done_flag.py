"""Add manual_editing_done flag to campaigns

Revision ID: 010
Revises: 009
Create Date: 2025-01-20 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    # Add manual_editing_done column to campaigns table
    op.add_column(
        'campaigns',
        sa.Column('manual_editing_done', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Create index for efficient queries
    op.create_index(
        'idx_campaigns_manual_editing_done',
        'campaigns',
        ['manual_editing_done'],
        unique=False
    )


def downgrade():
    # Drop index first
    op.drop_index('idx_campaigns_manual_editing_done', table_name='campaigns')
    
    # Drop column
    op.drop_column('campaigns', 'manual_editing_done')


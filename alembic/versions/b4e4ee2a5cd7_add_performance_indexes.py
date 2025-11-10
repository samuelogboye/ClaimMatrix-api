"""add_performance_indexes

Revision ID: b4e4ee2a5cd7
Revises: 
Create Date: 2025-11-10 21:52:21.177721

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4e4ee2a5cd7'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes to claims and audit_results tables."""

    # Claims table indexes
    # Index on date_of_service for date range queries and sorting
    op.create_index(
        'ix_claims_date_of_service',
        'claims',
        ['date_of_service'],
        unique=False
    )

    # Index on created_at for sorting recent claims
    op.create_index(
        'ix_claims_created_at',
        'claims',
        ['created_at'],
        unique=False
    )

    # Composite index for member_id queries with date sorting
    op.create_index(
        'ix_claims_member_date',
        'claims',
        ['member_id', 'date_of_service'],
        unique=False
    )

    # Composite index for provider_id queries with date sorting
    op.create_index(
        'ix_claims_provider_date',
        'claims',
        ['provider_id', 'date_of_service'],
        unique=False
    )

    # Audit Results table indexes
    # Index on audit_timestamp for sorting
    op.create_index(
        'ix_audit_results_audit_timestamp',
        'audit_results',
        ['audit_timestamp'],
        unique=False
    )

    # Index on suspicion_score for filtering flagged results
    op.create_index(
        'ix_audit_results_suspicion_score',
        'audit_results',
        ['suspicion_score'],
        unique=False
    )

    # Composite index for flagged audit queries (score filtering + timestamp sorting)
    op.create_index(
        'ix_audit_results_score_timestamp',
        'audit_results',
        ['suspicion_score', 'audit_timestamp'],
        unique=False
    )


def downgrade() -> None:
    """Remove performance indexes."""

    # Drop audit_results indexes
    op.drop_index('ix_audit_results_score_timestamp', table_name='audit_results')
    op.drop_index('ix_audit_results_suspicion_score', table_name='audit_results')
    op.drop_index('ix_audit_results_audit_timestamp', table_name='audit_results')

    # Drop claims indexes
    op.drop_index('ix_claims_provider_date', table_name='claims')
    op.drop_index('ix_claims_member_date', table_name='claims')
    op.drop_index('ix_claims_created_at', table_name='claims')
    op.drop_index('ix_claims_date_of_service', table_name='claims')

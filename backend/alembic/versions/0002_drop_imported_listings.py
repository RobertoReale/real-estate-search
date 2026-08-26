"""drop the email inbox import table

The inbox import subsystem is gone, and with it the only reader and writer of
`imported_listings`. Dropping a table is exactly the case the additive
migration path in `database._apply_additive_migrations` cannot express — it
only ever adds columns — so it is authored here.

The downgrade rebuilds the table (and its indexes) as the baseline had it, but
not its contents: the staged listings and, more importantly, the *discarded*
ones are gone for good. That asymmetry is deliberate and worth stating, because
those discard decisions were the memory that made an inbox re-scan idempotent.
Anyone reinstating the feature starts from an empty inbox history.

Revision ID: 0002_drop_imports
Revises: 0001_baseline
Create Date: 2026-08-26 10:12:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0002_drop_imports'
down_revision: Union[str, None] = '0001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Conditional because Alembic is not the only thing that builds this schema:
    # `init_db` runs `create_all` first, and on a fresh database that no longer
    # creates `imported_listings` at all — the model is gone. Alembic then stamps
    # the baseline and upgrades from it, so an unconditional drop would fail on
    # every brand-new install. The migration step is fail-open, so that failure
    # would be swallowed and the version would never advance past the baseline:
    # a silent, permanent retry loop on each startup.
    if not sa.inspect(op.get_bind()).has_table('imported_listings'):
        return

    with op.batch_alter_table('imported_listings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_imported_listings_status'))
        batch_op.drop_index(batch_op.f('ix_imported_listings_portal_id'))
        batch_op.drop_index(batch_op.f('ix_imported_listings_portal'))

    op.drop_table('imported_listings')


def downgrade() -> None:
    op.create_table(
        'imported_listings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('portal', sa.String(), nullable=False),
        sa.Column('portal_id', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('city', sa.String(), nullable=False),
        sa.Column('zone', sa.String(), nullable=False),
        sa.Column('rooms', sa.Integer(), nullable=True),
        sa.Column('sqm', sa.Float(), nullable=True),
        sa.Column('image_url', sa.String(), nullable=False, server_default=""),
        sa.Column('contract', sa.String(), nullable=False),
        sa.Column('email_from', sa.String(), nullable=False),
        sa.Column('email_subject', sa.String(), nullable=False),
        sa.Column('email_date', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('property_id', sa.Integer(), nullable=True),
        sa.Column('is_available', sa.Boolean(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('imported_listings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_imported_listings_portal'), ['portal'], unique=False)
        batch_op.create_index(
            batch_op.f('ix_imported_listings_portal_id'), ['portal_id'], unique=False
        )
        batch_op.create_index(batch_op.f('ix_imported_listings_status'), ['status'], unique=False)

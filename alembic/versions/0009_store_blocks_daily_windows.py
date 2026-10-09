"""Persist store blocks and transition hourly relations to daily Colombia windows.

Applied once under Alembic's durable revision marker. No startup rebasing.
Existing disabled (NULL next_check_at) relations and observations are untouched.
Generation increments invalidate any snapshot crossing the policy transition.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from alembic import op

revision = '0009_store_blocks_daily_windows'
down_revision = '0008_add_scraping_traffic'
branch_labels = None
depends_on = None


def _future_slot(group, now, checked):
    if checked is not None and checked.tzinfo is None:
        checked = checked.replace(tzinfo=UTC)
    threshold = max(now, checked) if checked is not None else now
    local = (threshold + timedelta(microseconds=1)).astimezone(ZoneInfo('America/Bogota'))
    for day in (0, 1):
        for hour in (8, 17):
            slot = (local + timedelta(days=day)).replace(hour=hour, minute=group * 20, second=0, microsecond=0)
            if slot >= local:
                return slot.astimezone(UTC)
    raise AssertionError('unreachable calendar')


def upgrade():
    op.create_table(
        'scraping_store_blocks',
        sa.Column('store_id', sa.String(36), sa.ForeignKey('stores.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('blocked_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reason', sa.String(50), nullable=False),
    )
    bind = op.get_bind()
    table = sa.table('book_store_relations',
                     sa.column('id', sa.String(36)), sa.column('scrape_group', sa.Integer()),
                     sa.column('next_check_at', sa.DateTime(timezone=True)),
                     sa.column('last_checked', sa.DateTime(timezone=True)),
                     sa.column('scrape_generation', sa.Integer()))
    now = datetime.now(UTC)
    rows = bind.execute(sa.select(table).where(table.c.next_check_at.is_not(None))).mappings()
    for row in rows:
        bind.execute(table.update().where(table.c.id == row['id']).values(
            next_check_at=_future_slot(row['scrape_group'], now, row['last_checked']),
            scrape_generation=table.c.scrape_generation + 1,
        ))


def downgrade():
    # Deliberately do not reconstruct old hourly timestamps or reset generations.
    # Application rollback must explicitly reconcile cadence before restarting.
    op.drop_table('scraping_store_blocks')

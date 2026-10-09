"""Append transport evidence, independent of price history.

Revision ID: 0008_add_scraping_traffic
Revises: 0007_add_scraping_schedule
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_add_scraping_traffic"
down_revision = "0007_add_scraping_schedule"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scraping_traffic_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("completeness", sa.String(24), nullable=False),
        sa.Column("scope", sa.String(24), nullable=False),
        sa.Column("batch_id", sa.String(36)),
        sa.Column("relation_id", sa.String(36)),
        sa.Column("operation_id", sa.String(36)),
        sa.Column("download_bytes", sa.BigInteger()),
        sa.Column("upload_bytes", sa.BigInteger()),
        sa.Column("request_bytes", sa.BigInteger()),
        sa.Column("header_bytes", sa.BigInteger()),
        sa.Column("redirects", sa.Integer()),
    )
    op.create_index("ix_traffic_date_scope", "scraping_traffic_events", ["observed_at", "scope"])
    op.create_index("ix_traffic_batch_date", "scraping_traffic_events", ["batch_id", "observed_at"])


def downgrade():
    op.drop_index("ix_traffic_batch_date", table_name="scraping_traffic_events")
    op.drop_index("ix_traffic_date_scope", table_name="scraping_traffic_events")
    op.drop_table("scraping_traffic_events")

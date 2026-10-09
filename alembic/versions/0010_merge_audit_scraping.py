"""Join audited ISBN normalization and daily scraping histories."""

revision = "0010_merge_audit_scraping"
down_revision = ("0007_normalize_isbn", "0009_store_blocks_daily_windows")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

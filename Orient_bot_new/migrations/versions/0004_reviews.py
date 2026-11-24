"""reviews

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("author_name", sa.String(128), nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("rating", sa.Integer, nullable=False, server_default="5"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reviews_status", "reviews", ["status"])

def downgrade() -> None:
    op.drop_index("ix_reviews_status", table_name="reviews")
    op.drop_table("reviews")
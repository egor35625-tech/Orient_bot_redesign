"""marketplace"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006" 

def upgrade():
    op.create_table(
        "marketplace_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(16), server_default="sell"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("price", sa.String(64)),
        sa.Column("currency", sa.String(8), server_default="BYN"),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("city", sa.String(128)),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "marketplace_photos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("marketplace_items.id"), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
    )

def downgrade():
    op.drop_table("marketplace_photos")
    op.drop_table("marketplace_items")
"""shop sync"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0009" # ПРОВЕРЬТЕ СВОЙ ПОСЛЕДНИЙ ID!

def upgrade():
    op.add_column("marketplace_items", sa.Column("shop_id", sa.Integer, sa.ForeignKey("shops.id"), nullable=True))

def downgrade():
    op.drop_column("marketplace_items", "shop_id")
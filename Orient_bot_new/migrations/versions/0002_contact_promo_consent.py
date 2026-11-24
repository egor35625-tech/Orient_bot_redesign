"""contact, promo, consent

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("orders", sa.Column("phone", sa.String(32), nullable=True))
    op.add_column("orders", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("orders", sa.Column("delivery_address", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("promo_code", sa.String(64), nullable=True))
    op.add_column("orders", sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_orders_promo_code", "orders", ["promo_code"])

def downgrade() -> None:
    op.drop_index("ix_orders_promo_code", table_name="orders")
    op.drop_column("orders", "consent_at")
    op.drop_column("orders", "promo_code")
    op.drop_column("orders", "delivery_address")
    op.drop_column("orders", "email")
    op.drop_column("orders", "phone")
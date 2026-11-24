"""order stages

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "order_stages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(64), unique=True, nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_final", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_rejected", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column("orders", sa.Column("current_stage_id", sa.Integer, sa.ForeignKey("order_stages.id"), nullable=True))
    op.create_index("ix_orders_current_stage_id", "orders", ["current_stage_id"])

    stages = [
        ("accepted", "Принят", 1, False, False),
        ("purchase", "Закупка", 2, False, False),
        ("shipping", "Отправка", 3, False, False),
        ("delivery", "Доставка", 4, False, False),
        ("done", "Готово", 5, True, False),
        ("rejected", "Отклонён", 6, True, True),
    ]
    op.bulk_insert(
        sa.table("order_stages",
                 sa.column("code", sa.String), sa.column("label", sa.String),
                 sa.column("position", sa.Integer), sa.column("is_final", sa.Boolean),
                 sa.column("is_rejected", sa.Boolean)),
        [{"code": c, "label": l, "position": p, "is_final": f, "is_rejected": r} for c, l, p, f, r in stages],
    )

def downgrade() -> None:
    op.drop_index("ix_orders_current_stage_id", table_name="orders")
    op.drop_column("orders", "current_stage_id")
    op.drop_table("order_stages")
"""shops, categories, delivery, countries

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"

def upgrade():
    # 1. Категории
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("icon", sa.String(64), nullable=True),
        sa.Column("position", sa.Integer, server_default="0"),
    )
    op.execute("""
        INSERT INTO categories (id, name, icon, position) VALUES 
        (1, 'Электроника', '📱', 1), (2, 'Одежда', '👕', 2), (3, 'Дом и сад', '🏠', 3),
        (4, 'Авто', '🚗', 4), (5, 'Услуги', '🛠', 5);
    """)
    op.execute("""
        INSERT INTO categories (id, parent_id, name, position) VALUES 
        (6, 1, 'Смартфоны', 1), (7, 1, 'Ноутбуки', 2), (8, 1, 'Аксессуары', 3),
        (9, 2, 'Мужское', 1), (10, 2, 'Женское', 2), (11, 2, 'Обувь', 3);
    """)
    
    # 2. Новые поля в товарах и профилях (Страны, Доставка)
    op.add_column("marketplace_items", sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id"), nullable=True))
    op.add_column("marketplace_items", sa.Column("views", sa.Integer, server_default="0"))
    op.add_column("marketplace_items", sa.Column("country", sa.String(8), server_default="BY"))
    op.add_column("marketplace_items", sa.Column("delivery_methods", sa.String(255), nullable=True))
    op.add_column("marketplace_items", sa.Column("pickup_address", sa.Text(), nullable=True))
    
    op.add_column("profiles", sa.Column("country", sa.String(8), server_default="BY"))

    # 3. Магазины и их этапы
    op.create_table(
        "shops",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_telegram_id", sa.BigInteger, unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("country", sa.String(8), server_default="BY"),
        sa.Column("logo", sa.String(1024)),
        sa.Column("boost_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "shop_stages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("position", sa.Integer, server_default="0"),
    )
    op.create_table(
        "shop_orders",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("marketplace_items.id"), nullable=False),
        sa.Column("buyer_telegram_id", sa.BigInteger, nullable=False),
        sa.Column("current_stage_id", sa.Integer, sa.ForeignKey("shop_stages.id")),
        sa.Column("status", sa.String(32), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table("shop_orders")
    op.drop_table("shop_stages")
    op.drop_table("shops")
    op.drop_column("profiles", "country")
    op.drop_column("marketplace_items", "pickup_address")
    op.drop_column("marketplace_items", "delivery_methods")
    op.drop_column("marketplace_items", "country")
    op.drop_column("marketplace_items", "views")
    op.drop_column("marketplace_items", "category_id")
    op.drop_table("categories")
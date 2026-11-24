"""shops applications, socials, reviews, order chat"""
from alembic import op
import sqlalchemy as sa


revision = "0012"
down_revision = "0011"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("profiles"):
        profile_cols = {c["name"] for c in inspector.get_columns("profiles")}
        if "country" not in profile_cols:
            op.add_column(
                "profiles",
                sa.Column("country", sa.String(8), server_default="BY"),
            )

    if not inspector.has_table("shop_applications"):
        op.create_table(
            "shop_applications",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("applicant_telegram_id", sa.BigInteger, nullable=False),
            sa.Column("shop_name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("country", sa.String(8), server_default="BY"),
            sa.Column("city", sa.String(128), nullable=True),
            sa.Column("manager_telegram_id", sa.BigInteger, nullable=True),
            sa.Column("manager_username", sa.String(255), nullable=True),
            sa.Column("instagram_url", sa.String(512), nullable=True),
            sa.Column("tiktok_url", sa.String(512), nullable=True),
            sa.Column("status", sa.String(32), server_default="pending"),
            sa.Column("reject_reason", sa.Text, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_shop_applications_applicant_telegram_id",
            "shop_applications",
            ["applicant_telegram_id"],
        )
        op.create_index(
            "ix_shop_applications_shop_name",
            "shop_applications",
            ["shop_name"],
            unique=True,
        )
        op.create_index(
            "ix_shop_applications_status",
            "shop_applications",
            ["status"],
        )

    if inspector.has_table("shops"):
        shop_cols = {c["name"] for c in inspector.get_columns("shops")}
        if "city" not in shop_cols:
            op.add_column("shops", sa.Column("city", sa.String(128), nullable=True))
        if "manager_telegram_id" not in shop_cols:
            op.add_column(
                "shops", sa.Column("manager_telegram_id", sa.BigInteger, nullable=True)
            )
        if "manager_username" not in shop_cols:
            op.add_column(
                "shops", sa.Column("manager_username", sa.String(255), nullable=True)
            )
        if "instagram_url" not in shop_cols:
            op.add_column(
                "shops", sa.Column("instagram_url", sa.String(512), nullable=True)
            )
        if "tiktok_url" not in shop_cols:
            op.add_column(
                "shops", sa.Column("tiktok_url", sa.String(512), nullable=True)
            )
        if "orders_count" not in shop_cols:
            op.add_column(
                "shops", sa.Column("orders_count", sa.Integer, server_default="0")
            )
        if "rating_avg" not in shop_cols:
            op.add_column(
                "shops", sa.Column("rating_avg", sa.Float, server_default="0.0")
            )
        if "reviews_count" not in shop_cols:
            op.add_column(
                "shops", sa.Column("reviews_count", sa.Integer, server_default="0")
            )

    if inspector.has_table("shop_orders"):
        order_cols = {c["name"] for c in inspector.get_columns("shop_orders")}
        if "updated_at" not in order_cols:
            op.add_column(
                "shop_orders",
                sa.Column(
                    "updated_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.func.now(),
                ),
            )

    if not inspector.has_table("shop_order_messages"):
        op.create_table(
            "shop_order_messages",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "shop_order_id",
                sa.Integer,
                sa.ForeignKey("shop_orders.id"),
                nullable=False,
            ),
            sa.Column("sender_telegram_id", sa.BigInteger, nullable=False),
            sa.Column("sender_role", sa.String(16), server_default="buyer"),
            sa.Column("text", sa.Text, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_shop_order_messages_shop_order_id",
            "shop_order_messages",
            ["shop_order_id"],
        )

    if not inspector.has_table("shop_reviews"):
        op.create_table(
            "shop_reviews",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "shop_id",
                sa.Integer,
                sa.ForeignKey("shops.id"),
                nullable=False,
            ),
            sa.Column("author_telegram_id", sa.BigInteger, nullable=False),
            sa.Column("author_name", sa.String(128), nullable=True),
            sa.Column("rating", sa.Integer, server_default="5"),
            sa.Column("text", sa.Text, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_shop_reviews_shop_id",
            "shop_reviews",
            ["shop_id"],
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("shop_reviews"):
        op.drop_table("shop_reviews")
    if inspector.has_table("shop_order_messages"):
        op.drop_table("shop_order_messages")
    if inspector.has_table("shop_applications"):
        op.drop_table("shop_applications")
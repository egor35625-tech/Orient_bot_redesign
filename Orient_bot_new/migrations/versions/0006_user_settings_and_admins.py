"""user settings and admins"""
from alembic import op
import sqlalchemy as sa
revision = "0006"
down_revision = "0005" # ВАЖНО: проверьте ваш предыдущий ID (может быть 0004)
def upgrade():
    op.add_column("users", sa.Column("language", sa.String(8), server_default="ru"))
    op.add_column("users", sa.Column("font_family", sa.String(32), server_default="system"))
    op.add_column("orders", sa.Column("admin_notes", sa.Text(), nullable=True))
    op.add_column("orders", sa.Column("is_read_by_admin", sa.Boolean(), server_default=sa.false()))
    op.add_column("orders", sa.Column("exported_to_sheets", sa.Boolean(), server_default=sa.false()))
    op.create_table("profiles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("phone", sa.String(32)),
        sa.Column("email", sa.String(255)),
        sa.Column("default_address", sa.Text),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table("admin_users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("telegram_id", sa.BigInteger, unique=True, nullable=False),
        sa.Column("added_by", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
def downgrade():
    op.drop_table("admin_users")
    op.drop_table("profiles")
    op.drop_column("orders", "exported_to_sheets")
    op.drop_column("orders", "is_read_by_admin")
    op.drop_column("orders", "admin_notes")
    op.drop_column("users", "font_family")
    op.drop_column("users", "language")
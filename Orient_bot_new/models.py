from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="ru")
    font_family: Mapped[str] = mapped_column(String(32), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    profile: Mapped["Profile | None"] = relationship(
        back_populates="user", uselist=False
    )
    shop: Mapped["Shop | None"] = relationship(
        back_populates="owner", uselist=False
    )


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str] = mapped_column(String(8), default="BY")
    default_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    # @username в Telegram, указанный при регистрации (без @). Регистрация = заполненный tg_username.
    tg_username: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="profile")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    added_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(128))
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class ShopApplication(Base):
    __tablename__ = "shop_applications"
    __table_args__ = (Index("ix_shop_applications_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    applicant_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    shop_name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str] = mapped_column(String(8), default="BY")
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    manager_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    manager_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    instagram_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tiktok_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # 'create' — новый магазин, 'edit' — изменение существующего (shop_id).
    kind: Mapped[str] = mapped_column(String(16), default="create", server_default="create")
    shop_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # None — аватар не менять, "" — удалить, иначе путь к новому файлу.
    logo: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contact_mode: Mapped[str] = mapped_column(String(16), default="messages", server_default="messages")
    pickup_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_methods: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Shop(Base):
    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_telegram_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), unique=True
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str] = mapped_column(String(8), default="BY")
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    manager_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    manager_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    instagram_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    tiktok_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    logo: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Контакты и доставка магазина: подставляются во все объявления магазина.
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contact_mode: Mapped[str] = mapped_column(String(16), default="messages", server_default="messages")
    pickup_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_methods: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Модерация: active | blocked (blocked_until=None => навсегда). Время — naive UTC.
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    orders_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0)
    reviews_count: Mapped[int] = mapped_column(Integer, default=0)
    boost_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    owner: Mapped["User"] = relationship(back_populates="shop")
    stages: Mapped[list["ShopStage"]] = relationship(
        back_populates="shop", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["ShopReview"]] = relationship(
        back_populates="shop", cascade="all, delete-orphan"
    )


class ShopStage(Base):
    __tablename__ = "shop_stages"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"))
    label: Mapped[str] = mapped_column(String(128))
    position: Mapped[int] = mapped_column(Integer, default=0)

    shop: Mapped["Shop"] = relationship(back_populates="stages")


class MarketplaceItem(Base):
    __tablename__ = "marketplace_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    shop_id: Mapped[int | None] = mapped_column(
        ForeignKey("shops.id"), nullable=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(16), default="sell")
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price_value: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(8), default="BYN")
    # Необязательный телефон ("" если не указан). У объявлений магазина берётся из магазина.
    phone: Mapped[str] = mapped_column(String(32), default="")
    contact_mode: Mapped[str] = mapped_column(String(16), default="messages", server_default="messages")
    search_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country: Mapped[str] = mapped_column(String(8), default="BY")
    delivery_methods: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pickup_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship()
    shop: Mapped["Shop | None"] = relationship()
    photos: Mapped[list["MarketplacePhoto"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class MarketplacePhoto(Base):
    __tablename__ = "marketplace_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("marketplace_items.id"))
    file_path: Mapped[str] = mapped_column(String(1024))

    item: Mapped["MarketplaceItem"] = relationship(back_populates="photos")


class ShopOrder(Base):
    __tablename__ = "shop_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("marketplace_items.id"))
    buyer_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    current_stage_id: Mapped[int | None] = mapped_column(
        ForeignKey("shop_stages.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    shop: Mapped["Shop"] = relationship()
    item: Mapped["MarketplaceItem"] = relationship()
    current_stage: Mapped["ShopStage | None"] = relationship()
    messages: Mapped[list["ShopOrderMessage"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class ShopOrderMessage(Base):
    __tablename__ = "shop_order_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_order_id: Mapped[int] = mapped_column(
        ForeignKey("shop_orders.id"), index=True
    )
    sender_telegram_id: Mapped[int] = mapped_column(BigInteger)
    sender_role: Mapped[str] = mapped_column(String(16), default="buyer")
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    order: Mapped["ShopOrder"] = relationship(back_populates="messages")


class ShopReview(Base):
    __tablename__ = "shop_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    author_telegram_id: Mapped[int] = mapped_column(BigInteger)
    author_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rating: Mapped[int] = mapped_column(Integer, default=5)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    shop: Mapped["Shop"] = relationship(back_populates="reviews")


class OrderStage(Base):
    __tablename__ = "order_stages"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    label: Mapped[str] = mapped_column(String(128))
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    is_rejected: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    description: Mapped[str] = mapped_column(Text)
    additional_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    promo_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    price: Mapped[str | None] = mapped_column(String(64), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="€")
    status: Mapped[str] = mapped_column(String(32), default="active")
    current_stage_id: Mapped[int | None] = mapped_column(
        ForeignKey("order_stages.id"), nullable=True, index=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True, index=True
    )
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read_by_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    exported_to_sheets: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="orders")
    photos: Mapped[list["OrderPhoto"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    current_stage: Mapped["OrderStage | None"] = relationship(lazy="joined")


class OrderPhoto(Base):
    __tablename__ = "order_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    file_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_path: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    order: Mapped["Order"] = relationship(back_populates="photos")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    sender_id: Mapped[int] = mapped_column(BigInteger)
    message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_type: Mapped[str] = mapped_column(String(32), default="text")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    order: Mapped["Order"] = relationship(back_populates="messages")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (Index("ix_reviews_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    rating: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
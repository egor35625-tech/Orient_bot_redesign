from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    username: str | None = None
    first_name: str | None = None


class ProfileOut(BaseModel):
    first_name: str | None = None
    telegram_username: str | None = None  # username из Telegram (подсказка для регистрации)
    tg_username: str | None = None  # @username, указанный при регистрации
    city: str | None = None
    default_address: str | None = None
    is_registered: bool = False
    is_admin: bool = False


class ProfileUpdate(BaseModel):
    tg_username: str | None = None
    city: str | None = None
    default_address: str | None = None


class PhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_path: str
    file_id: str | None = None


class MarketPhotoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_path: str


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int | None = None
    name: str
    icon: str | None = None
    position: int = 0


class ShopStageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shop_id: int
    label: str
    position: int


class ShopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_telegram_id: int
    name: str
    description: str | None = None
    country: str = "BY"
    city: str | None = None
    manager_telegram_id: int | None = None
    manager_username: str | None = None
    instagram_url: str | None = None
    tiktok_url: str | None = None
    logo: str | None = None
    phone: str | None = None
    contact_mode: str = "messages"
    pickup_address: str | None = None
    delivery_methods: str | None = None
    status: str = "active"
    blocked_until: datetime | None = None
    block_reason: str | None = None
    orders_count: int = 0
    rating_avg: float = 0.0
    reviews_count: int = 0
    boost_until: datetime | None = None
    created_at: datetime
    stages: list[ShopStageOut] = []


class ShopBrief(BaseModel):
    id: int
    name: str
    logo: str | None = None
    status: str = "active"


class ShopApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    applicant_telegram_id: int
    kind: str = "create"
    shop_id: int | None = None
    shop_name: str
    description: str | None = None
    country: str
    city: str | None = None
    manager_telegram_id: int | None = None
    manager_username: str | None = None
    instagram_url: str | None = None
    tiktok_url: str | None = None
    logo: str | None = None
    phone: str | None = None
    contact_mode: str = "messages"
    pickup_address: str | None = None
    delivery_methods: str | None = None
    status: str
    reject_reason: str | None = None
    created_at: datetime


class ShopApplicationReject(BaseModel):
    reason: str | None = None


class ShopBlockIn(BaseModel):
    days: int | None = Field(default=None, ge=1, le=3650)  # None => навсегда
    reason: str | None = None


class ShopReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5, default=5)
    text: str = Field(min_length=1, max_length=2000)
    author_name: str | None = None


class ShopReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shop_id: int
    author_telegram_id: int
    author_name: str | None = None
    rating: int
    text: str
    created_at: datetime


class ShopOrderMessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=3000)


class ShopOrderMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shop_order_id: int
    sender_telegram_id: int
    sender_role: str
    text: str
    created_at: datetime


class ShopOrderStageSet(BaseModel):
    stage_id: int


class OrderItemBrief(BaseModel):
    id: int
    title: str
    price: str | None = None
    currency: str = "BYN"


class ShopOrderOut(BaseModel):
    id: int
    shop_id: int
    item_id: int
    buyer_telegram_id: int
    buyer_username: str | None = None
    status: str
    current_stage_id: int | None = None
    current_stage: ShopStageOut | None = None
    created_at: datetime
    item: OrderItemBrief | None = None
    shop: ShopBrief | None = None
    shop_stages: list[ShopStageOut] = []


class MarketItemOut(BaseModel):
    id: int
    shop_id: int | None = None
    category_id: int | None = None
    title: str
    description: str
    price: str | None = None
    currency: str = "BYN"
    phone: str = ""
    contact_mode: str = "messages"
    city: str | None = None
    country: str = "BY"
    delivery_methods: str | None = None
    pickup_address: str | None = None
    views: int = 0
    created_at: datetime
    seller_username: str | None = None
    is_mine: bool = False
    shop: ShopBrief | None = None
    photos: list[MarketPhotoOut] = []


class MyItemsOut(BaseModel):
    private: list[MarketItemOut] = []
    shop: list[MarketItemOut] = []


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender_id: int
    message_text: str | None = None
    message_type: str
    created_at: datetime


class StageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    label: str
    position: int
    is_final: bool
    is_rejected: bool


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int | None = None
    author_name: str | None = None
    text: str
    rating: int
    status: str
    created_at: datetime


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    additional_comment: str | None = None
    phone: str | None = None
    email: str | None = None
    delivery_address: str | None = None
    promo_code: str | None = None
    price: str | None = None
    currency: str
    status: str
    admin_notes: str | None = None
    current_stage: StageOut | None = None
    created_at: datetime
    photos: list[PhotoOut] = []
    messages: list[MessageOut] = []
    user: UserOut | None = None


class OrderListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    description: str
    price: str | None = None
    created_at: datetime
    current_stage: StageOut | None = None


class StatusUpdate(BaseModel):
    status: str


class PriceUpdate(BaseModel):
    price: str
    currency: str = "€"


class ReplyMessage(BaseModel):
    text: str


class ReviewCreate(BaseModel):
    order_id: int | None = None
    author_name: str | None = None
    text: str = Field(min_length=1, max_length=2000)
    rating: int = Field(ge=1, le=5, default=5)


class StageCreate(BaseModel):
    label: str
    code: str | None = None
    position: int | None = None


class StageUpdate(BaseModel):
    label: str | None = None
    position: int | None = None


class StageReorder(BaseModel):
    ids: list[int]


class AdminNotesUpdate(BaseModel):
    notes: str


class AdminUserCreate(BaseModel):
    telegram_id: int


class BulkStageUpdate(BaseModel):
    order_ids: list[int]
    stage_id: int


class BulkAction(BaseModel):
    order_ids: list[int]
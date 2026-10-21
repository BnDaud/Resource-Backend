import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.crypto import EncryptedInt, EncryptedText, blind_index, search_tokens
from app.core.db import Base


class Role(str, enum.Enum):
    admin = "admin"
    editor = "editor"


class Availability(str, enum.Enum):
    available = "available"
    out_of_stock = "out_of_stock"
    on_request = "on_request"
    discontinued = "discontinued"


class Section(str, enum.Enum):
    boards = "boards"
    accessories = "accessories"


class PriceMode(str, enum.Enum):
    request = "request"
    public = "public"


class CustomerType(str, enum.Enum):
    wholesale = "wholesale"
    retail = "retail"


class QuoteStatus(str, enum.Enum):
    new = "new"
    under_review = "under_review"
    quoted = "quoted"
    accepted = "accepted"
    rejected = "rejected"
    closed = "closed"


class EnquiryStatus(str, enum.Enum):
    new = "new"
    read = "read"
    replied = "replied"
    archived = "archived"


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Staff(Base, Timestamped):
    __tablename__ = "staff"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(EncryptedText)
    email_hash: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # blind index for login lookup
    name: Mapped[str] = mapped_column(EncryptedText)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False, length=20), default=Role.editor)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    @validates("email")
    def _email(self, _key, value: str) -> str:
        value = value.strip().lower()
        self.email_hash = blind_index(value)
        return value


class Category(Base, Timestamped):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    section: Mapped[Section] = mapped_column(Enum(Section, native_enum=False, length=20), default=Section.accessories, index=True)  # which division of the shop it belongs to
    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base, Timestamped):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("public_price IS NULL OR public_price >= 0", name="ck_product_price_nonneg"),
        Index("ix_products_listing", "is_archived", "category_id", "availability"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))  # public id used in URLs and APIs
    name: Mapped[str] = mapped_column(String(200), index=True)
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    brand: Mapped[str] = mapped_column(String(120), default="")
    short_description: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    availability: Mapped[Availability] = mapped_column(Enum(Availability, native_enum=False, length=20), default=Availability.on_request)
    price_mode: Mapped[PriceMode] = mapped_column(Enum(PriceMode, native_enum=False, length=20), default=PriceMode.request)
    public_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    wholesale_note: Mapped[str] = mapped_column(EncryptedText, default="")  # staff only
    stock_qty: Mapped[int | None] = mapped_column(EncryptedInt, nullable=True)  # staff only
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[Category] = relationship(back_populates="products")
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductImage.sort_order"
    )
    specs: Mapped[list["ProductSpec"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductSpec.sort_order"
    )
    options: Mapped[list["AttributeOption"]] = relationship(secondary="product_options", order_by="AttributeOption.sort_order")  # finish, colour, size, ...


class Attribute(Base):
    """A choice a category (or a whole division) offers, such as Finish, Colour or Size. It is a filter on the website and,
    when `customer_picks` is set, something the customer chooses when adding the product to a quote."""
    __tablename__ = "attributes"
    __table_args__ = (CheckConstraint("(category_id IS NULL) <> (section IS NULL)", name="ck_attribute_one_scope"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), nullable=True, index=True)
    section: Mapped[Section | None] = mapped_column(Enum(Section, native_enum=False, length=20), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(60))
    filterable: Mapped[bool] = mapped_column(Boolean, default=True)
    customer_picks: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    options: Mapped[list["AttributeOption"]] = relationship(
        back_populates="attribute", cascade="all, delete-orphan", order_by="AttributeOption.sort_order"
    )


class AttributeOption(Base):
    __tablename__ = "attribute_options"
    id: Mapped[int] = mapped_column(primary_key=True)
    attribute_id: Mapped[int] = mapped_column(ForeignKey("attributes.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(60))
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # swatch, like #c0392b
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    attribute: Mapped[Attribute] = relationship(back_populates="options")


product_options = Table(
    "product_options", Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("option_id", ForeignKey("attribute_options.id", ondelete="CASCADE"), primary_key=True),
)


class ProductImage(Base):
    __tablename__ = "product_images"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    storage_path: Mapped[str] = mapped_column(String(300))
    alt: Mapped[str] = mapped_column(String(200), default="")
    is_main: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    product: Mapped[Product] = relationship(back_populates="images")


class ProductSpec(Base):
    __tablename__ = "product_specs"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    value: Mapped[str] = mapped_column(String(300))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    product: Mapped[Product] = relationship(back_populates="specs")


class QuoteRequest(Base, Timestamped):
    __tablename__ = "quote_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))  # public id used in URLs and APIs
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(EncryptedText)
    customer_type: Mapped[CustomerType] = mapped_column(Enum(CustomerType, native_enum=False, length=20))
    phone: Mapped[str] = mapped_column(EncryptedText)
    email: Mapped[str] = mapped_column(EncryptedText, default="")
    company: Mapped[str] = mapped_column(EncryptedText, default="")
    message: Mapped[str] = mapped_column(EncryptedText, default="")
    preferred_contact: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[QuoteStatus] = mapped_column(Enum(QuoteStatus, native_enum=False, length=20), default=QuoteStatus.new, index=True)
    internal_notes: Mapped[str] = mapped_column(EncryptedText, default="")
    search_tokens: Mapped[str] = mapped_column(Text, default="")  # blind indexes of name words + phone
    items: Mapped[list["QuoteItem"]] = relationship(back_populates="quote", cascade="all, delete-orphan")


class QuoteItem(Base):
    __tablename__ = "quote_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_quote_item_qty_pos"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quote_requests.id", ondelete="CASCADE"), index=True)
    # SET NULL keeps the request intact if the product row is ever removed.
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(200))
    product_sku: Mapped[str] = mapped_column(String(64))
    spec_note: Mapped[str] = mapped_column(String(300), default="")
    quantity: Mapped[int] = mapped_column(Integer)
    quote: Mapped[QuoteRequest] = relationship(back_populates="items")
    product: Mapped["Product | None"] = relationship()

    @property
    def product_uid(self) -> str | None:
        return self.product.uid if self.product else None


def _enquiry_reference() -> str:
    from app.services.common import new_reference

    return new_reference(datetime.now(timezone.utc), "EN")


class Enquiry(Base, Timestamped):
    __tablename__ = "enquiries"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True, default=_enquiry_reference)
    uid: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))  # public id used in URLs and APIs
    name: Mapped[str] = mapped_column(EncryptedText)
    email: Mapped[str] = mapped_column(EncryptedText, default="")
    phone: Mapped[str] = mapped_column(EncryptedText)
    subject: Mapped[str] = mapped_column(EncryptedText)
    message: Mapped[str] = mapped_column(EncryptedText)
    status: Mapped[EnquiryStatus] = mapped_column(Enum(EnquiryStatus, native_enum=False, length=20), default=EnquiryStatus.new, index=True)
    internal_notes: Mapped[str] = mapped_column(EncryptedText, default="")
    search_tokens: Mapped[str] = mapped_column(Text, default="")


class Testimonial(Base, Timestamped):
    __tablename__ = "testimonials"
    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(160))
    company: Mapped[str] = mapped_column(String(160), default="")
    text: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class SiteSettings(Base):
    __tablename__ = "site_settings"
    __table_args__ = (UniqueConstraint("id", name="uq_site_settings_single"), CheckConstraint("id = 1", name="ck_site_settings_singleton"))
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    business_name: Mapped[str] = mapped_column(String(160), default="Resources Components")
    address: Mapped[str] = mapped_column(String(300), default="13 Amu Street, Off Palm Avenue, Mushin, Lagos State, Nigeria")
    opening_hours: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    whatsapp_number: Mapped[str] = mapped_column(String(20), default="")
    whatsapp_message: Mapped[str] = mapped_column(
        String(300), default="Hello Resources Components, I'm interested in your products and would like to make an enquiry."
    )
    instagram_url: Mapped[str] = mapped_column(String(300), default="")
    tiktok_url: Mapped[str] = mapped_column(String(300), default="")
    seo_title: Mapped[str] = mapped_column(String(160), default="Resources Components")
    seo_description: Mapped[str] = mapped_column(String(320), default="")


@event.listens_for(QuoteRequest, "before_insert")
@event.listens_for(QuoteRequest, "before_update")
def _quote_tokens(_m, _c, t: QuoteRequest):
    t.search_tokens = search_tokens(t.full_name, t.company, phone=t.phone)


@event.listens_for(Enquiry, "before_insert")
@event.listens_for(Enquiry, "before_update")
def _enquiry_tokens(_m, _c, t: Enquiry):
    t.search_tokens = search_tokens(t.name, t.subject, phone=t.phone)

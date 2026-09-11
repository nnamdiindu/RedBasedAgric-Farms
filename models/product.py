from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    slug = Column(String(160), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    description = Column(Text, default="")
    specs = Column(JSON, default=dict)
    nutrition_facts = Column(JSON, default=list)
    image_primary = Column(String(255), nullable=False)
    image_gallery = Column(JSON, default=list)
    badge = Column(String(50), nullable=True)
    rating_score = Column(Float, default=0)
    rating_count = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False, nullable=False)
    is_bestseller = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    variants = relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductVariant.price",
    )

    @property
    def in_stock(self) -> bool:
        return any(variant.stock_qty > 0 for variant in self.variants)

    @property
    def min_price(self):
        prices = [variant.price for variant in self.variants]
        return min(prices) if prices else None


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    size_label = Column(String(50), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    stock_qty = Column(Integer, default=0, nullable=False)
    sku = Column(String(50), unique=True, nullable=True)
    image = Column(String(255), nullable=True)
    image_gallery = Column(JSON, default=list)

    product = relationship("Product", back_populates="variants")

    @property
    def in_stock(self) -> bool:
        return self.stock_qty > 0

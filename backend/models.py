"""
ShilpSetu – SQLAlchemy ORM models.

Tables
------
- clusters       Geographic artisan clusters.
- artisans       Individual artisan profiles.
- products       Cataloged craft products (with 384-d vector embedding).
- rfqs           Request-for-Quotation workflow records.
- search_trends  Aggregated search / demand signals.

The `products.embedding` column uses pgvector's `Vector(384)` type on
PostgreSQL and falls back to a JSON-text representation on SQLite so
local development works without native extensions.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base, IS_POSTGRES

# ---------------------------------------------------------------------------
# Conditional vector column type
# ---------------------------------------------------------------------------
if IS_POSTGRES:
    from pgvector.sqlalchemy import Vector as PgVector

    _VECTOR_TYPE = PgVector(384)
else:
    # Fallback: store embeddings as JSON text in SQLite
    _VECTOR_TYPE = Text()


def _uuid_pk() -> str:
    """Generate a new UUID4 hex string for use as a primary key."""
    return uuid.uuid4().hex


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CLUSTERS                                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=_uuid_pk
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    primary_craft: Mapped[str] = mapped_column(String(120), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    combined_monthly_capacity: Mapped[int] = mapped_column(
        Integer, default=0
    )

    # Relationships
    artisans: Mapped[list["Artisan"]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan"
    )
    rfqs: Mapped[list["RFQ"]] = relationship(
        back_populates="cluster", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Cluster {self.name!r} ({self.district}, {self.state})>"


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  ARTISANS                                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class Artisan(Base):
    __tablename__ = "artisans"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=_uuid_pk
    )
    cluster_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clusters.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    native_dialect: Mapped[str] = mapped_column(
        String(10), nullable=False, doc="ISO 639-1 language code (gu, hi, bn …)"
    )
    phone: Mapped[str] = mapped_column(String(15), nullable=False)
    rating: Mapped[float] = mapped_column(Float, default=4.8)
    verification_status: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_wage_baseline: Mapped[float] = mapped_column(Float, nullable=False)
    pin_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Relationships
    cluster: Mapped["Cluster"] = relationship(back_populates="artisans")
    products: Mapped[list["Product"]] = relationship(
        back_populates="artisan", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Artisan {self.name!r} dialect={self.native_dialect}>"


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  PRODUCTS                                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=_uuid_pk
    )
    artisan_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("artisans.id"), nullable=False
    )
    title_en: Mapped[str] = mapped_column(String(300), nullable=False)
    title_hi: Mapped[str] = mapped_column(String(300), nullable=False)
    craft_type: Mapped[str] = mapped_column(String(120), nullable=False)
    material: Mapped[str] = mapped_column(String(120), nullable=False)
    raw_cost: Mapped[float] = mapped_column(Float, nullable=False)
    labor_days: Mapped[float] = mapped_column(Float, nullable=False)
    recommended_price: Mapped[float] = mapped_column(Float, nullable=False)
    min_market_corridor: Mapped[float] = mapped_column(Float, nullable=False)
    max_market_corridor: Mapped[float] = mapped_column(Float, nullable=False)
    raw_image_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    studio_image_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    embedding = Column("embedding", _VECTOR_TYPE, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    artisan: Mapped["Artisan"] = relationship(back_populates="products")

    def __repr__(self) -> str:
        return f"<Product {self.title_en!r} ₹{self.recommended_price}>"


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  RFQS (Request for Quotation)                                           ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class RFQ(Base):
    __tablename__ = "rfqs"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=_uuid_pk
    )
    buyer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    cluster_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("clusters.id"), nullable=False
    )
    target_units: Mapped[int] = mapped_column(Integer, nullable=False)
    specifications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    offered_unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING",
        doc="One of: PENDING, ALLOCATED, DISPATCHED",
    )

    # Relationships
    cluster: Mapped["Cluster"] = relationship(back_populates="rfqs")

    def __repr__(self) -> str:
        return f"<RFQ buyer={self.buyer_name!r} status={self.status}>"


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  SEARCH TRENDS                                                          ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

class SearchTrend(Base):
    __tablename__ = "search_trends"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=_uuid_pk
    )
    query: Mapped[str] = mapped_column(String(300), nullable=False)
    craft_category: Mapped[str] = mapped_column(String(120), nullable=False)
    search_count: Mapped[int] = mapped_column(Integer, default=0)
    region: Mapped[str] = mapped_column(String(100), nullable=False)

    def __repr__(self) -> str:
        return f"<SearchTrend {self.query!r} ×{self.search_count}>"

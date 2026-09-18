"""
HunarPath – Public catalog router.

Provides product listing and search for the web dashboard.
No authentication required (buyer-facing, public).
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_session
from models import Artisan, Cluster, Product
from schemas import CatalogProductListResponse, CatalogProductResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/catalog", tags=["Catalog"])


def _product_to_response(product: Product) -> CatalogProductResponse:
    """Convert a Product ORM instance (with loaded relationships) to a response."""
    artisan = product.artisan
    cluster = artisan.cluster if artisan else None
    return CatalogProductResponse(
        id=product.id,
        title_en=product.title_en,
        title_hi=product.title_hi,
        craft_type=product.craft_type,
        material=product.material,
        raw_cost=product.raw_cost,
        labor_days=product.labor_days,
        recommended_price=product.recommended_price,
        min_market_corridor=product.min_market_corridor,
        max_market_corridor=product.max_market_corridor,
        studio_image_path=product.studio_image_path,
        is_active=product.is_active,
        artisan_name=artisan.name if artisan else "Unknown",
        cluster_name=cluster.name if cluster else "Unknown",
        rating=artisan.rating if artisan else 4.8,
    )


@router.get("/products", response_model=CatalogProductListResponse, summary="List all active products")
async def list_products(
    session: AsyncSession = Depends(get_session),
):
    """Return all active products with artisan and cluster details."""
    stmt = (
        select(Product)
        .where(Product.is_active.is_(True))
        .options(
            selectinload(Product.artisan).selectinload(Artisan.cluster)
        )
        .order_by(Product.recommended_price.desc())
    )
    result = await session.execute(stmt)
    products = list(result.scalars().all())

    return CatalogProductListResponse(
        products=[_product_to_response(p) for p in products],
        total=len(products),
    )


@router.get("/products/search", response_model=CatalogProductListResponse, summary="Search products")
async def search_products(
    q: str = Query(..., min_length=1, description="Search query"),
    session: AsyncSession = Depends(get_session),
):
    """Search active products by title, craft type, or material using SQL LIKE."""
    pattern = f"%{q}%"
    stmt = (
        select(Product)
        .where(
            Product.is_active.is_(True),
            or_(
                Product.title_en.ilike(pattern),
                Product.title_hi.ilike(pattern),
                Product.craft_type.ilike(pattern),
                Product.material.ilike(pattern),
            ),
        )
        .options(
            selectinload(Product.artisan).selectinload(Artisan.cluster)
        )
        .order_by(Product.recommended_price.desc())
    )
    result = await session.execute(stmt)
    products = list(result.scalars().all())

    return CatalogProductListResponse(
        products=[_product_to_response(p) for p in products],
        total=len(products),
    )

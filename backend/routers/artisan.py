"""
ShilpSetu – Artisan profile, dashboard, and orders router.

All endpoints require JWT authentication.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models import Artisan, Cluster, Product, RFQ
from schemas import (
    ArtisanProfileResponse,
    DashboardMetricsResponse,
    OrderShareResponse,
)
from services.auth_service import get_current_artisan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/artisan", tags=["Artisan"])


@router.get("/me", response_model=ArtisanProfileResponse, summary="Get current artisan profile")
async def get_profile(
    artisan: Artisan = Depends(get_current_artisan),
    session: AsyncSession = Depends(get_session),
):
    """Return the authenticated artisan's profile."""
    cluster = await session.get(Cluster, artisan.cluster_id)
    cluster_name = cluster.name if cluster else "Unknown"

    return ArtisanProfileResponse(
        id=artisan.id,
        name=artisan.name,
        phone=artisan.phone,
        cluster_id=artisan.cluster_id,
        cluster_name=cluster_name,
        dialect=artisan.native_dialect,
        rating=artisan.rating,
        verified=artisan.verification_status,
    )


@router.get("/me/dashboard", response_model=DashboardMetricsResponse, summary="Get dashboard metrics")
async def get_dashboard(
    artisan: Artisan = Depends(get_current_artisan),
    session: AsyncSession = Depends(get_session),
):
    """Compute live dashboard metrics for the authenticated artisan."""
    # Count active products
    product_count = await session.execute(
        select(func.count(Product.id)).where(
            Product.artisan_id == artisan.id,
            Product.is_active.is_(True),
        )
    )
    active_items = product_count.scalar() or 0

    # Count RFQs allocated to this artisan's cluster
    order_result = await session.execute(
        select(func.count(RFQ.id), func.coalesce(func.sum(RFQ.offered_unit_price * RFQ.target_units), 0.0)).where(
            RFQ.cluster_id == artisan.cluster_id,
            RFQ.status == "ALLOCATED",
        )
    )
    row = order_result.one()
    total_orders = row[0] or 0
    total_cluster_earnings = float(row[1] or 0.0)

    # Approximate artisan's share (proportional by wage baseline)
    artisans_in_cluster = await session.execute(
        select(func.count(Artisan.id), func.coalesce(func.sum(Artisan.daily_wage_baseline), 1.0)).where(
            Artisan.cluster_id == artisan.cluster_id,
            Artisan.verification_status.is_(True),
        )
    )
    cluster_row = artisans_in_cluster.one()
    total_wage = float(cluster_row[1] or 1.0)
    artisan_share = artisan.daily_wage_baseline / total_wage if total_wage > 0 else 0.0
    total_earnings = round(total_cluster_earnings * artisan_share, 2)

    return DashboardMetricsResponse(
        active_items=active_items,
        total_orders=total_orders,
        total_earnings=total_earnings,
    )


@router.get("/me/orders", response_model=list[OrderShareResponse], summary="Get artisan's order allocations")
async def get_orders(
    artisan: Artisan = Depends(get_current_artisan),
    session: AsyncSession = Depends(get_session),
):
    """Return RFQ allocations for the artisan's cluster with computed share."""
    # Get all allocated RFQs for this artisan's cluster
    stmt = (
        select(RFQ)
        .where(
            RFQ.cluster_id == artisan.cluster_id,
            RFQ.status.in_(["ALLOCATED", "DISPATCHED"]),
        )
        .order_by(RFQ.id.desc())
    )
    result = await session.execute(stmt)
    rfqs = list(result.scalars().all())

    if not rfqs:
        return []

    # Compute artisan's proportional share
    artisans_result = await session.execute(
        select(func.coalesce(func.sum(Artisan.daily_wage_baseline), 1.0)).where(
            Artisan.cluster_id == artisan.cluster_id,
            Artisan.verification_status.is_(True),
        )
    )
    total_wage = float(artisans_result.scalar() or 1.0)
    share_ratio = artisan.daily_wage_baseline / total_wage if total_wage > 0 else 0.0

    orders = []
    for rfq in rfqs:
        allocated_units = max(1, round(rfq.target_units * share_ratio))
        payout = round(allocated_units * rfq.offered_unit_price, 2)
        orders.append(OrderShareResponse(
            rfq_id=rfq.id,
            buyer_name=rfq.buyer_name,
            allocated_units=allocated_units,
            payout_amount=payout,
            status=rfq.status,
        ))

    return orders

"""
HunarPath – Demand Radar Service.

Aggregates search-trend data from the ``search_trends`` table and
synthesises plain-language demand notifications in the artisan's
native dialect so they can act on real-time market signals.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import SearchTrend

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dialect notification templates
# ---------------------------------------------------------------------------
# {craft} – craft category, {pct} – percentage change, {region} – region,
# {price} – target price

_NOTIFICATION_TEMPLATES: dict[str, str] = {
    "en": (
        "Demand for {craft} increased {pct}% in {region} region. "
        "Target market price: {price} rupees."
    ),
    "hi": (
        "{region} क्षेत्र में {craft} की माँग {pct}% बढ़ी है। "
        "लक्ष्य बाज़ार मूल्य: ₹{price}।"
    ),
    "gu": (
        "{region} વિસ્તારમાં {craft} ની માંગ {pct}% વધી છે। "
        "લક્ષ્ય બજાર ભાવ: ₹{price}."
    ),
    "bn": (
        "{region} অঞ্চলে {craft}-এর চাহিদা {pct}% বেড়েছে। "
        "লক্ষ্য বাজার মূল্য: ₹{price}।"
    ),
    "ta": (
        "{region} பகுதியில் {craft} தேவை {pct}% அதிகரித்துள்ளது. "
        "இலக்கு சந்தை விலை: ₹{price}."
    ),
    "te": (
        "{region} ప్రాంతంలో {craft} డిమాండ్ {pct}% పెరిగింది. "
        "లక్ష్య మార్కెట్ ధర: ₹{price}."
    ),
    "mr": (
        "{region} भागात {craft} ची मागणी {pct}% वाढली आहे। "
        "लक्ष्य बाजार भाव: ₹{price}."
    ),
}

# Rough baseline thresholds per craft for percentage-change estimation
_BASELINE_SEARCH_COUNTS: dict[str, int] = {
    "Zari & Brocade": 12000,
    "Bell Metal Craft": 3500,
    "Embroidery": 5000,
    "Block Printing": 4000,
    "Handloom Weaving": 6000,
    "Mirror Work": 3000,
    "Meenakari": 2500,
    "Wood Carving": 2000,
    "Wrought Iron": 1500,
    "Terracotta": 2000,
}

# Approximate market price signals per craft (₹) – used for notification text
_TARGET_PRICE_HINTS: dict[str, int] = {
    "Zari & Brocade": 2200,
    "Bell Metal Craft": 1800,
    "Embroidery": 950,
    "Block Printing": 1400,
    "Handloom Weaving": 1600,
    "Mirror Work": 1100,
    "Meenakari": 1500,
    "Wood Carving": 1600,
    "Wrought Iron": 700,
    "Terracotta": 450,
}

DEFAULT_BASELINE: int = 3000
DEFAULT_TARGET_PRICE: int = 1000


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

async def get_top_trends(
    session: AsyncSession,
    *,
    craft_category: Optional[str] = None,
    region: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """
    Return the top trending search queries ordered by ``search_count``
    descending, optionally filtered by craft category and/or region.
    """
    stmt = select(SearchTrend).order_by(desc(SearchTrend.search_count))

    if craft_category:
        stmt = stmt.where(SearchTrend.craft_category == craft_category)
    if region:
        stmt = stmt.where(SearchTrend.region == region)

    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "id": row.id,
            "query": row.query,
            "craft_category": row.craft_category,
            "search_count": row.search_count,
            "region": row.region,
        }
        for row in rows
    ]


async def get_demand_summary(
    session: AsyncSession,
    *,
    limit: int = 5,
) -> list[dict]:
    """
    Aggregate search counts by craft category and return top categories
    with total demand volume.
    """
    stmt = (
        select(
            SearchTrend.craft_category,
            func.sum(SearchTrend.search_count).label("total_searches"),
            func.count(SearchTrend.id).label("query_count"),
        )
        .group_by(SearchTrend.craft_category)
        .order_by(desc("total_searches"))
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "craft_category": row.craft_category,
            "total_searches": row.total_searches,
            "query_count": row.query_count,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Notification synthesis
# ---------------------------------------------------------------------------

def _estimate_pct_change(craft_category: str, current_count: int) -> int:
    """Estimate percentage demand change vs. the historical baseline."""
    baseline = _BASELINE_SEARCH_COUNTS.get(craft_category, DEFAULT_BASELINE)
    if baseline <= 0:
        return 0
    return max(0, round(((current_count - baseline) / baseline) * 100))


def synthesize_demand_notification(
    craft_category: str,
    search_count: int,
    region: str,
    dialect: str = "hi",
) -> str:
    """
    Generate a plain-language demand notification in the artisan's
    native dialect.

    Parameters
    ----------
    craft_category : str
        Craft category from the trend data.
    search_count : int
        Current aggregate search count.
    region : str
        Geographic region label.
    dialect : str
        ISO 639-1 language code (``hi``, ``gu``, ``bn``, etc.).

    Returns
    -------
    str
        Human-readable notification string.
    """
    pct = _estimate_pct_change(craft_category, search_count)
    price = _TARGET_PRICE_HINTS.get(craft_category, DEFAULT_TARGET_PRICE)
    template = _NOTIFICATION_TEMPLATES.get(dialect, _NOTIFICATION_TEMPLATES["en"])

    return template.format(
        craft=craft_category,
        pct=pct,
        region=region,
        price=price,
    )


async def generate_demand_alerts(
    session: AsyncSession,
    dialect: str = "hi",
    limit: int = 5,
) -> list[dict]:
    """
    Fetch the top search trends, compute percentage changes, and return
    ready-to-deliver notification payloads.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    dialect : str
        Target language for notification text.
    limit : int
        Maximum number of alerts.

    Returns
    -------
    list[dict]
        Each dict contains ``craft_category``, ``region``,
        ``search_count``, ``pct_change``, and ``notification``.
    """
    trends = await get_top_trends(session, limit=limit)
    alerts: list[dict] = []

    for trend in trends:
        craft = trend["craft_category"]
        count = trend["search_count"]
        region = trend["region"]
        pct = _estimate_pct_change(craft, count)

        notification = synthesize_demand_notification(
            craft_category=craft,
            search_count=count,
            region=region,
            dialect=dialect,
        )

        alerts.append(
            {
                "craft_category": craft,
                "region": region,
                "search_count": count,
                "pct_change": pct,
                "notification": notification,
            }
        )

    logger.info("Generated %d demand alerts (dialect=%s).", len(alerts), dialect)
    return alerts

"""
HunarPath - Mock / seed data generator.

Creates:
  • 3 geographic clusters (Kachchh, Varanasi, Bastar)
  • 10 verified artisans spread across clusters
  • 15 cataloged products with synthetic 384-d vector embeddings
  • 5 sample search-trend rows

Run standalone:
    python mock_data.py          # seeds the local SQLite dev DB

Or call `seed()` programmatically from an async context.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid

import numpy as np
from sqlalchemy import select

from database import IS_POSTGRES, async_session_factory, init_db
from models import Artisan, Cluster, Product, RFQ, SearchTrend

logger = logging.getLogger(__name__)

# Default demo PIN hash for '1234' - pre-computed to avoid bcrypt overhead during seeding
_DEFAULT_PIN_HASH: str | None = None

def _get_default_pin_hash() -> str:
    global _DEFAULT_PIN_HASH
    if _DEFAULT_PIN_HASH is None:
        from services.auth_service import hash_pin
        _DEFAULT_PIN_HASH = hash_pin("1234")
    return _DEFAULT_PIN_HASH

# Deterministic randomness for reproducible seeds
_RNG = np.random.default_rng(seed=42)
random.seed(42)


def _uid() -> str:
    return uuid.uuid4().hex


def _synthetic_embedding(dim: int = 384) -> list[float]:
    """Generate a unit-norm random embedding vector."""
    vec = _RNG.standard_normal(dim).astype(np.float32)
    vec /= np.linalg.norm(vec)
    return vec.tolist()


# ---------------------------------------------------------------------------
# Raw seed data
# ---------------------------------------------------------------------------

CLUSTERS_DATA = [
    {
        "id": _uid(),
        "name": "Kachchh Weaving Cluster",
        "state": "Gujarat",
        "district": "Kachchh",
        "primary_craft": "Handloom Weaving",
        "latitude": 23.7337,
        "longitude": 69.8597,
        "combined_monthly_capacity": 1200,
    },
    {
        "id": _uid(),
        "name": "Varanasi Zari Cluster",
        "state": "Uttar Pradesh",
        "district": "Varanasi",
        "primary_craft": "Zari & Brocade",
        "latitude": 25.3176,
        "longitude": 83.0068,
        "combined_monthly_capacity": 2500,
    },
    {
        "id": _uid(),
        "name": "Bastar Bell Metal Cluster",
        "state": "Chhattisgarh",
        "district": "Bastar",
        "primary_craft": "Bell Metal Craft",
        "latitude": 19.1071,
        "longitude": 81.9535,
        "combined_monthly_capacity": 800,
    },
]

ARTISANS_DATA = [
    # --- Kachchh (cluster 0) ---
    {
        "name": "Ramji Vankar",
        "native_dialect": "gu",
        "phone": "+919876500001",
        "rating": 4.9,
        "daily_wage_baseline": 450.0,
    },
    {
        "name": "Fatima Khatri",
        "native_dialect": "gu",
        "phone": "+919876500002",
        "rating": 4.7,
        "daily_wage_baseline": 420.0,
    },
    {
        "name": "Lakha Marwada",
        "native_dialect": "gu",
        "phone": "+919876500003",
        "rating": 4.8,
        "daily_wage_baseline": 400.0,
    },
    # --- Varanasi (cluster 1) ---
    {
        "name": "Mohammad Irfan Ansari",
        "native_dialect": "hi",
        "phone": "+919876500004",
        "rating": 4.9,
        "daily_wage_baseline": 550.0,
    },
    {
        "name": "Suresh Prasad",
        "native_dialect": "hi",
        "phone": "+919876500005",
        "rating": 4.6,
        "daily_wage_baseline": 500.0,
    },
    {
        "name": "Rekha Devi",
        "native_dialect": "hi",
        "phone": "+919876500006",
        "rating": 4.8,
        "daily_wage_baseline": 480.0,
    },
    {
        "name": "Akhtar Hussain",
        "native_dialect": "hi",
        "phone": "+919876500007",
        "rating": 4.7,
        "daily_wage_baseline": 520.0,
    },
    # --- Bastar (cluster 2) ---
    {
        "name": "Manglu Ram Gond",
        "native_dialect": "hi",
        "phone": "+919876500008",
        "rating": 4.8,
        "daily_wage_baseline": 380.0,
    },
    {
        "name": "Phoolbasan Yadav",
        "native_dialect": "hi",
        "phone": "+919876500009",
        "rating": 4.9,
        "daily_wage_baseline": 370.0,
    },
    {
        "name": "Bhulan Singh Dhurwa",
        "native_dialect": "hi",
        "phone": "+919876500010",
        "rating": 4.5,
        "daily_wage_baseline": 360.0,
    },
]

# Cluster assignment: first 3 -> Kachchh, next 4 -> Varanasi, last 3 -> Bastar
_ARTISAN_CLUSTER_MAP = [0, 0, 0, 1, 1, 1, 1, 2, 2, 2]

PRODUCTS_DATA = [
    # --- Kachchh products ---
    {
        "title_en": "Patola Silk Dupatta",
        "title_hi": "पटोला सिल्क दुपट्टा",
        "craft_type": "Handloom Weaving",
        "material": "Silk",
        "raw_cost": 800.0,
        "labor_days": 5.0,
        "recommended_price": 3500.0,
        "min_market_corridor": 2800.0,
        "max_market_corridor": 4200.0,
        "artisan_idx": 0,
    },
    {
        "title_en": "Kutchi Embroidered Cushion Cover",
        "title_hi": "कच्छी कढ़ाई कुशन कवर",
        "craft_type": "Embroidery",
        "material": "Cotton",
        "raw_cost": 200.0,
        "labor_days": 2.0,
        "recommended_price": 950.0,
        "min_market_corridor": 750.0,
        "max_market_corridor": 1200.0,
        "artisan_idx": 1,
    },
    {
        "title_en": "Ajrakh Block-Print Stole",
        "title_hi": "अजरख ब्लॉक-प्रिंट स्टोल",
        "craft_type": "Block Printing",
        "material": "Cotton",
        "raw_cost": 300.0,
        "labor_days": 3.0,
        "recommended_price": 1400.0,
        "min_market_corridor": 1100.0,
        "max_market_corridor": 1800.0,
        "artisan_idx": 0,
    },
    {
        "title_en": "Rabari Mirror-Work Bag",
        "title_hi": "रबारी मिरर-वर्क बैग",
        "craft_type": "Mirror Work",
        "material": "Cotton & Mirrors",
        "raw_cost": 250.0,
        "labor_days": 2.5,
        "recommended_price": 1100.0,
        "min_market_corridor": 850.0,
        "max_market_corridor": 1400.0,
        "artisan_idx": 2,
    },
    {
        "title_en": "Kachchhi Wool Shawl",
        "title_hi": "कच्छी ऊन शॉल",
        "craft_type": "Handloom Weaving",
        "material": "Wool",
        "raw_cost": 600.0,
        "labor_days": 4.0,
        "recommended_price": 2800.0,
        "min_market_corridor": 2200.0,
        "max_market_corridor": 3400.0,
        "artisan_idx": 2,
    },
    # --- Varanasi products ---
    {
        "title_en": "Banarasi Silk Saree",
        "title_hi": "बनारसी सिल्क साड़ी",
        "craft_type": "Zari & Brocade",
        "material": "Silk & Gold Zari",
        "raw_cost": 3500.0,
        "labor_days": 15.0,
        "recommended_price": 18000.0,
        "min_market_corridor": 14000.0,
        "max_market_corridor": 25000.0,
        "artisan_idx": 3,
    },
    {
        "title_en": "Zari Brocade Clutch",
        "title_hi": "ज़री ब्रोकेड क्लच",
        "craft_type": "Zari & Brocade",
        "material": "Silk & Zari",
        "raw_cost": 400.0,
        "labor_days": 3.0,
        "recommended_price": 1800.0,
        "min_market_corridor": 1400.0,
        "max_market_corridor": 2200.0,
        "artisan_idx": 4,
    },
    {
        "title_en": "Brocade Table Runner",
        "title_hi": "ब्रोकेड टेबल रनर",
        "craft_type": "Zari & Brocade",
        "material": "Silk",
        "raw_cost": 500.0,
        "labor_days": 4.0,
        "recommended_price": 2200.0,
        "min_market_corridor": 1700.0,
        "max_market_corridor": 2800.0,
        "artisan_idx": 5,
    },
    {
        "title_en": "Banarasi Silk Tie",
        "title_hi": "बनारसी सिल्क टाई",
        "craft_type": "Zari & Brocade",
        "material": "Silk & Zari",
        "raw_cost": 250.0,
        "labor_days": 1.5,
        "recommended_price": 1200.0,
        "min_market_corridor": 900.0,
        "max_market_corridor": 1600.0,
        "artisan_idx": 6,
    },
    {
        "title_en": "Gulabi Meenakari Tray",
        "title_hi": "गुलाबी मीनाकारी ट्रे",
        "craft_type": "Meenakari",
        "material": "Copper & Enamel",
        "raw_cost": 350.0,
        "labor_days": 2.0,
        "recommended_price": 1500.0,
        "min_market_corridor": 1200.0,
        "max_market_corridor": 1900.0,
        "artisan_idx": 3,
    },
    # --- Bastar products ---
    {
        "title_en": "Dhokra Elephant Figurine",
        "title_hi": "ढोकरा हाथी मूर्ति",
        "craft_type": "Bell Metal Craft",
        "material": "Bell Metal (Brass)",
        "raw_cost": 450.0,
        "labor_days": 4.0,
        "recommended_price": 2500.0,
        "min_market_corridor": 2000.0,
        "max_market_corridor": 3200.0,
        "artisan_idx": 7,
    },
    {
        "title_en": "Tribal Iron Wind Chime",
        "title_hi": "ट्राइबल आयरन विंड चाइम",
        "craft_type": "Wrought Iron",
        "material": "Iron",
        "raw_cost": 150.0,
        "labor_days": 1.5,
        "recommended_price": 700.0,
        "min_market_corridor": 550.0,
        "max_market_corridor": 900.0,
        "artisan_idx": 8,
    },
    {
        "title_en": "Bastar Wooden Mask",
        "title_hi": "बस्तर लकड़ी मुखौटा",
        "craft_type": "Wood Carving",
        "material": "Teak Wood",
        "raw_cost": 300.0,
        "labor_days": 3.0,
        "recommended_price": 1600.0,
        "min_market_corridor": 1200.0,
        "max_market_corridor": 2000.0,
        "artisan_idx": 9,
    },
    {
        "title_en": "Bell Metal Diya Set (4 pcs)",
        "title_hi": "बेल मेटल दीया सेट (4 पीस)",
        "craft_type": "Bell Metal Craft",
        "material": "Bell Metal (Brass)",
        "raw_cost": 500.0,
        "labor_days": 3.5,
        "recommended_price": 2200.0,
        "min_market_corridor": 1800.0,
        "max_market_corridor": 2800.0,
        "artisan_idx": 7,
    },
    {
        "title_en": "Chhattisgarhi Terracotta Pot",
        "title_hi": "छत्तीसगढ़ी टेराकोटा मटका",
        "craft_type": "Terracotta",
        "material": "Clay",
        "raw_cost": 100.0,
        "labor_days": 1.0,
        "recommended_price": 450.0,
        "min_market_corridor": 350.0,
        "max_market_corridor": 600.0,
        "artisan_idx": 9,
    },
]

SEARCH_TRENDS_DATA = [
    {"query": "banarasi saree", "craft_category": "Zari & Brocade", "search_count": 18400, "region": "North India"},
    {"query": "dhokra art", "craft_category": "Bell Metal Craft", "search_count": 5200, "region": "Central India"},
    {"query": "kutchi embroidery cushion", "craft_category": "Embroidery", "search_count": 7800, "region": "West India"},
    {"query": "ajrakh print fabric", "craft_category": "Block Printing", "search_count": 6100, "region": "West India"},
    {"query": "handmade brass diya", "craft_category": "Bell Metal Craft", "search_count": 12300, "region": "Pan India"},
]


# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------

async def seed() -> None:
    """
    Populate the database with mock data.

    Safe to call multiple times - skips seeding if clusters already exist.
    """
    await init_db()

    async with async_session_factory() as session:
        # Guard: skip if data already present
        result = await session.execute(select(Cluster).limit(1))
        if result.scalars().first() is not None:
            logger.info("Database already seeded - skipping.")
            return

        # ── Clusters ──────────────────────────────────────────────────
        cluster_objs: list[Cluster] = []
        for c in CLUSTERS_DATA:
            cluster = Cluster(**c)
            session.add(cluster)
            cluster_objs.append(cluster)

        await session.flush()  # ensure cluster IDs are available

        # ── Artisans ─────────────────────────────────────────────────
        artisan_objs: list[Artisan] = []
        for idx, a in enumerate(ARTISANS_DATA):
            cluster_idx = _ARTISAN_CLUSTER_MAP[idx]
            artisan = Artisan(
                id=_uid(),
                cluster_id=cluster_objs[cluster_idx].id,
                verification_status=True,
                pin_hash=_get_default_pin_hash(),
                **a,
            )
            session.add(artisan)
            artisan_objs.append(artisan)

        await session.flush()

        # ── Products ─────────────────────────────────────────────────
        # Note: No hardcoded mock products seeded. Only products published
        # by artisans through the HunarPath mobile app will appear.

        # ── Search Trends ────────────────────────────────────────────
        for st in SEARCH_TRENDS_DATA:
            trend = SearchTrend(id=_uid(), **st)
            session.add(trend)

        await session.commit()
        logger.info(
            "Seeded %d clusters, %d artisans, 0 mock products, %d search trends.",
            len(cluster_objs),
            len(artisan_objs),
            len(SEARCH_TRENDS_DATA),
        )


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    asyncio.run(seed())
    print("Database seeded successfully.")

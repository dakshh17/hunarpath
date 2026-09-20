"""
HunarPath AI - Primary FastAPI Application Gateway.

Connects Flutter mobile / Next.js web clients to the AI service layer:
  • Catalog ingest  (vision + ASR + cataloger + pricing - concurrent)
  • Catalog publish  (persist product + vector embedding)
  • Clusters map     (GeoJSON for map widgets)
  • RFQ aggregation  (proportional artisan allocation)
  • Demand radar     (trend alerts in artisan dialect)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import dispose_engine, get_session, init_db, IS_POSTGRES
from models import Artisan, Cluster, Product, RFQ, SearchTrend
from schemas import (
    ArtisanAllocation,
    CatalogIngestResponse,
    CatalogMetadata,
    ClusterGeoFeature,
    ClusterGeoJSON,
    ClusterGeoProperties,
    DemandAlert,
    DemandRadarResponse,
    PriceRecommendation,
    ProductRead,
    PublishRequest,
    PublishResponse,
    RFQAggregateRequest,
    RFQAggregateResponse,
)
from services.bhashini_service import transcribe_indic_audio
from services.cataloger_service import extract_and_translate_catalog
from services.demand_radar import generate_demand_alerts
from services.pricing_service import calculate_price_recommendation
from services.vision_service import process_studio_image

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run DB migrations & seed mock data on startup; dispose pool on shutdown."""
    # Run DB migrations (with graceful retry & fallback for transient cloud network startup)
    db_initialized = False
    for attempt in range(1, 4):
        try:
            logger.info("Initializing database connection (attempt %d/3)...", attempt)
            await init_db()
            db_initialized = True
            logger.info("Database schema initialized successfully.")
            break
        except Exception as exc:
            logger.warning("Database init failed on attempt %d: %s", attempt, exc)
            if attempt < 3:
                await asyncio.sleep(2)

    if db_initialized:
        try:
            from mock_data import seed as seed_database
            await seed_database()
            logger.info("Base cluster & artisan seeding completed.")

            # Purge legacy mock products without studio images
            # so the marketplace strictly contains genuine artisan-published products
            from database import async_session_factory
            from sqlalchemy import delete
            async with async_session_factory() as session:
                del_stmt = delete(Product).where(Product.studio_image_path.is_(None))
                result = await session.execute(del_stmt)
                await session.commit()
                if result.rowcount > 0:
                    logger.info("Purged %d legacy mock products without studio images.", result.rowcount)
        except Exception:
            logger.exception("Startup data setup encountered an issue - continuing.")
    else:
        logger.error("Could not connect to external DB during startup. Backend will continue booting.")

    yield

    logger.info("Shutting down HunarPath AI backend ...")
    await dispose_engine()


# ---------------------------------------------------------------------------
# App & Middleware
# ---------------------------------------------------------------------------

app = FastAPI(
    title="HunarPath AI Backend Engine",
    description=(
        "API gateway for the HunarPath artisan empowerment platform.  "
        "Provides AI-powered catalog ingestion, fair pricing, GeoJSON "
        "cluster maps, RFQ aggregation, and demand-radar alerts."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
from routers.auth import router as auth_router
from routers.artisan import router as artisan_router
from routers.catalog import router as catalog_router

app.include_router(auth_router)
app.include_router(artisan_router)
app.include_router(catalog_router)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RNG = np.random.default_rng(seed=0)


def _synthetic_embedding(dim: int = 384) -> list[float]:
    """Generate a unit-norm random 384-d embedding (placeholder for a real
    encoder such as sentence-transformers/all-MiniLM-L6-v2)."""
    vec = _RNG.standard_normal(dim).astype(np.float32)
    vec /= np.linalg.norm(vec)
    return vec.tolist()


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  POST /api/v1/catalog/ingest                                            ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

@app.post(
    "/api/v1/catalog/ingest",
    response_model=CatalogIngestResponse,
    summary="Ingest raw product photo + artisan voice → studio image, catalog, price",
    tags=["Catalog"],
)
async def catalog_ingest(
    image: UploadFile = File(..., description="Raw product photograph"),
    audio: Optional[UploadFile] = File(None, description="Artisan voice note (optional if transcript sent)"),
    transcript: Optional[str] = Form(None, description="Live speech-to-text transcript from mobile device"),
    language: str = Form("hi", description="ISO 639-1 dialect code"),
    artisan_id: str = Form(..., description="Artisan UUID"),
):
    """
    Concurrently processes the product image and artisan voice note / live transcript,
    then chains the transcript through the cataloger and pricing
    services. Returns a unified payload ready for client review.
    """
    # Read uploaded bytes
    image_bytes = await image.read()
    audio_bytes = await audio.read() if audio else b""

    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file.")

    # ── 1. Vision Studio Processing (with 15s safety timeout) ─────────
    try:
        studio_bytes = await asyncio.wait_for(
            asyncio.to_thread(process_studio_image, image_bytes),
            timeout=15.0,
        )
    except Exception as exc:
        logger.warning("Studio vision processing timed out or failed (%s); using original image.", exc)
        studio_bytes = image_bytes

    # ── 2. Resolve Transcript: Client Live STT vs Backend ASR ─────────
    resolved_transcript = ""
    if transcript and transcript.strip():
        resolved_transcript = transcript.strip()
        logger.info("Using on-device live transcript provided by client: '%s'", resolved_transcript)
    elif audio_bytes:
        try:
            resolved_transcript = await asyncio.wait_for(
                transcribe_indic_audio(audio_bytes, lang_code=language),
                timeout=8.0,
            )
        except Exception as exc:
            logger.warning("ASR timed out or failed (%s); falling back to default.", exc)
            resolved_transcript = "हस्तनिर्मित उत्पाद"
    else:
        resolved_transcript = "हस्तनिर्मित शिल्प उत्पाद"

    # ── 3. Cataloger → Pricing ─────────────────────────────────────────
    try:
        catalog_data = await asyncio.wait_for(
            extract_and_translate_catalog(resolved_transcript),
            timeout=12.0,
        )
    except Exception as exc:
        logger.warning("Catalog extraction timed out (%s); using regex fallback.", exc)
        from services.cataloger_service import _regex_fallback_catalog
        catalog_data = _regex_fallback_catalog(resolved_transcript)

    raw_cost = catalog_data.get("raw_cost") or 0.0
    labor_days = catalog_data.get("labor_days") or 1.0
    craft_type = catalog_data.get("craft_type") or "Handloom Weaving"

    price_data = calculate_price_recommendation(
        raw_cost=raw_cost,
        labor_days=labor_days,
        craft_type=craft_type,
    )

    # ── Assemble response ─────────────────────────────────────────────
    studio_b64 = base64.b64encode(studio_bytes).decode("ascii")

    return CatalogIngestResponse(
        studio_image_base64=studio_b64,
        raw_transcript=resolved_transcript,
        catalog_metadata=CatalogMetadata(**catalog_data),
        price_recommendation=PriceRecommendation(**price_data),
        artisan_id=artisan_id,
    )


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  POST /api/v1/speech/transcribe                                         ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

@app.post(
    "/api/v1/speech/transcribe",
    summary="Transcribe artisan voice note using Groq Whisper",
    tags=["Speech"],
)
async def speech_transcribe(
    audio: UploadFile = File(..., description="Artisan voice note audio file"),
    language: str = Form("hi", description="ISO 639-1 dialect code"),
):
    """
    Direct transcription endpoint using Groq Whisper (whisper-large-v3-turbo).
    Provides rapid (<500ms) speech recognition for Indian dialects.
    """
    audio_bytes = await audio.read()
    if not audio_bytes or len(audio_bytes) < 50:
        return {"transcript": ""}

    try:
        text = await asyncio.wait_for(
            transcribe_indic_audio(audio_bytes, lang_code=language),
            timeout=10.0,
        )
        return {"transcript": text}
    except Exception as exc:
        logger.warning("Speech transcription endpoint failed (%s)", exc)
        return {"transcript": ""}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  POST /api/v1/catalog/publish                                           ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

@app.post(
    "/api/v1/catalog/publish",
    response_model=PublishResponse,
    summary="Persist an approved product and generate its search embedding",
    tags=["Catalog"],
)
async def catalog_publish(
    payload: PublishRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Commits the approved product record to the ``products`` table,
    generates a 384-d vector embedding for semantic search, and
    updates the artisan's cluster active count.
    """
    # Validate artisan exists
    artisan = await session.get(Artisan, payload.artisan_id)
    if artisan is None:
        raise HTTPException(status_code=404, detail="Artisan not found.")

    # Generate embedding
    embedding_vec = _synthetic_embedding()
    embedding_stored = True

    # For SQLite fallback, store embedding as JSON string
    if not IS_POSTGRES:
        embedding_value = json.dumps(embedding_vec)
    else:
        embedding_value = embedding_vec

    product = Product(
        id=uuid.uuid4().hex,
        artisan_id=payload.artisan_id,
        title_en=payload.title_en,
        title_hi=payload.title_hi,
        craft_type=payload.craft_type,
        material=payload.material,
        raw_cost=payload.raw_cost,
        labor_days=payload.labor_days,
        recommended_price=payload.recommended_price,
        min_market_corridor=payload.min_market_corridor,
        max_market_corridor=payload.max_market_corridor,
        raw_image_path=payload.raw_image_path,
        studio_image_path=payload.studio_image_path,
        embedding=embedding_value,
        is_active=payload.is_active,
    )
    session.add(product)

    # Update cluster combined_monthly_capacity (increment by 1 as proxy
    # for "one more active product available")
    cluster = await session.get(Cluster, artisan.cluster_id)
    if cluster:
        cluster.combined_monthly_capacity = (
            cluster.combined_monthly_capacity + 1
        )

    # Session commit handled by get_session dependency
    await session.flush()

    return PublishResponse(
        product_id=product.id,
        title_en=product.title_en,
        recommended_price=product.recommended_price,
        embedding_stored=embedding_stored,
        message="Product published and embedding stored successfully.",
    )


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  GET /api/v1/clusters/map                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

@app.get(
    "/api/v1/clusters/map",
    response_model=ClusterGeoJSON,
    summary="GeoJSON FeatureCollection of all artisan clusters",
    tags=["Clusters"],
)
async def clusters_map(
    session: AsyncSession = Depends(get_session),
):
    """
    Returns a GeoJSON payload with every cluster as a Point feature,
    annotated with active artisan counts, combined monthly capacity,
    and coordinates for map rendering.
    """
    # Subquery: active (verified) artisan count per cluster
    artisan_count_sq = (
        select(
            Artisan.cluster_id,
            func.count(Artisan.id).label("active_artisan_count"),
        )
        .where(Artisan.verification_status.is_(True))
        .group_by(Artisan.cluster_id)
        .subquery()
    )

    stmt = (
        select(Cluster, artisan_count_sq.c.active_artisan_count)
        .outerjoin(
            artisan_count_sq,
            Cluster.id == artisan_count_sq.c.cluster_id,
        )
        .order_by(Cluster.name)
    )

    result = await session.execute(stmt)
    rows = result.all()

    features: list[ClusterGeoFeature] = []
    for cluster, artisan_count in rows:
        features.append(
            ClusterGeoFeature(
                geometry={
                    "type": "Point",
                    "coordinates": [cluster.longitude, cluster.latitude],
                },
                properties=ClusterGeoProperties(
                    id=cluster.id,
                    name=cluster.name,
                    state=cluster.state,
                    district=cluster.district,
                    primary_craft=cluster.primary_craft,
                    combined_monthly_capacity=cluster.combined_monthly_capacity,
                    active_artisan_count=artisan_count or 0,
                ),
            )
        )

    return ClusterGeoJSON(features=features)


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  POST /api/v1/rfq/aggregate                                            ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

@app.post(
    "/api/v1/rfq/aggregate",
    response_model=RFQAggregateResponse,
    summary="Submit an RFQ and receive a proportional allocation ledger",
    tags=["RFQ"],
)
async def rfq_aggregate(
    payload: RFQAggregateRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Accepts a buyer RFQ, validates the target cluster, splits units
    proportionally across verified artisans by their daily wage
    baseline (as a capacity proxy), creates an RFQ record, and returns
    the allocation ledger with individual payout amounts.
    """
    # Validate cluster
    cluster = await session.get(Cluster, payload.cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Cluster not found.")

    # Fetch verified artisans in this cluster
    stmt = (
        select(Artisan)
        .where(
            Artisan.cluster_id == payload.cluster_id,
            Artisan.verification_status.is_(True),
        )
        .order_by(Artisan.name)
    )
    result = await session.execute(stmt)
    artisans: list[Artisan] = list(result.scalars().all())

    if not artisans:
        raise HTTPException(
            status_code=422,
            detail="No verified artisans available in this cluster.",
        )

    # ── Proportional allocation ───────────────────────────────────────
    # Weight = inverse of daily_wage_baseline (cheaper artisans have
    # higher capacity; alternatively could use a dedicated capacity
    # column).  Here we use wage as a simple proportional weight.
    weights = np.array(
        [a.daily_wage_baseline for a in artisans], dtype=np.float64
    )
    # Normalise so shares sum to 1
    total_weight = weights.sum()
    if total_weight == 0:
        shares = np.ones(len(artisans)) / len(artisans)
    else:
        shares = weights / total_weight

    # Distribute units (floor each, assign remainders by largest remainder)
    raw_units = shares * payload.target_units
    floor_units = np.floor(raw_units).astype(int)
    remainders = raw_units - floor_units
    deficit = payload.target_units - floor_units.sum()

    # Assign leftover units to artisans with the largest fractional parts
    if deficit > 0:
        top_indices = np.argsort(-remainders)[:deficit]
        for idx in top_indices:
            floor_units[idx] += 1

    # Build allocation entries
    allocations: list[ArtisanAllocation] = []
    for artisan, units in zip(artisans, floor_units):
        payout = round(float(units) * payload.target_unit_price, 2)
        allocations.append(
            ArtisanAllocation(
                artisan_id=artisan.id,
                artisan_name=artisan.name,
                allocated_units=int(units),
                payout_amount=payout,
            )
        )

    # ── Persist RFQ record ────────────────────────────────────────────
    rfq = RFQ(
        id=uuid.uuid4().hex,
        buyer_name=payload.buyer_name,
        cluster_id=payload.cluster_id,
        target_units=payload.target_units,
        specifications=payload.custom_specs,
        offered_unit_price=payload.target_unit_price,
        status="ALLOCATED",
    )
    session.add(rfq)
    await session.flush()

    total_value = round(payload.target_units * payload.target_unit_price, 2)

    return RFQAggregateResponse(
        rfq_id=rfq.id,
        buyer_name=payload.buyer_name,
        cluster_id=payload.cluster_id,
        total_units=payload.target_units,
        unit_price=payload.target_unit_price,
        total_value=total_value,
        status="ALLOCATED",
        allocations=allocations,
    )


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  GET /api/v1/demand-radar                                               ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

@app.get(
    "/api/v1/demand-radar",
    response_model=DemandRadarResponse,
    summary="Trending demand alerts with dialect-localised notifications",
    tags=["Demand Radar"],
)
async def demand_radar(
    cluster_id: Optional[str] = None,
    dialect: str = "hi",
    limit: int = 5,
    session: AsyncSession = Depends(get_session),
):
    """
    Queries the ``search_trends`` table, computes percentage demand
    shifts, and returns notification strings localised to the artisan's
    dialect for push / audio delivery on the mobile app.
    """
    if cluster_id:
        cluster = await session.get(Cluster, cluster_id)
        if cluster is None:
            raise HTTPException(status_code=404, detail="Cluster not found.")

    raw_alerts = await generate_demand_alerts(
        session, dialect=dialect, limit=limit
    )

    alerts = [DemandAlert(**a) for a in raw_alerts]

    return DemandRadarResponse(
        cluster_id=cluster_id,
        dialect=dialect,
        alerts=alerts,
    )


# ---------------------------------------------------------------------------
# Health-check & Root Index
# ---------------------------------------------------------------------------

@app.get("/", tags=["Ops"], summary="Root endpoint")
async def root():
    return {
        "service": "HunarPath AI Platform Gateway",
        "status": "online",
        "docs": "/docs",
        "health": "/healthz",
    }


@app.get("/healthz", tags=["Ops"], summary="Liveness probe")
async def healthz():
    return {"status": "ok", "service": "hunarpath-ai-backend"}

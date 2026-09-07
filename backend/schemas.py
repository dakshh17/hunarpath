"""
ShilpSetu – Pydantic v2 request / response schemas.

These mirror the ORM models and are used by FastAPI for automatic
validation, serialization, and OpenAPI documentation.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  CORE ENTITY SCHEMAS                                                    ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

# ---------------------------------------------------------------------------
# Cluster
# ---------------------------------------------------------------------------

class ClusterBase(BaseModel):
    name: str
    state: str
    district: str
    primary_craft: str
    latitude: float
    longitude: float
    combined_monthly_capacity: int = 0


class ClusterCreate(ClusterBase):
    pass


class ClusterRead(ClusterBase):
    id: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Artisan
# ---------------------------------------------------------------------------

class ArtisanBase(BaseModel):
    cluster_id: str
    name: str
    native_dialect: str = Field(
        ..., max_length=10, description="ISO 639-1 code, e.g. gu, hi, bn"
    )
    phone: str = Field(..., max_length=15)
    rating: float = 4.8
    verification_status: bool = True
    daily_wage_baseline: float


class ArtisanCreate(ArtisanBase):
    pass


class ArtisanRead(ArtisanBase):
    id: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

class ProductBase(BaseModel):
    artisan_id: str
    title_en: str
    title_hi: str
    craft_type: str
    material: str
    raw_cost: float
    labor_days: float
    recommended_price: float
    min_market_corridor: float
    max_market_corridor: float
    raw_image_path: Optional[str] = None
    studio_image_path: Optional[str] = None
    is_active: bool = True


class ProductCreate(ProductBase):
    embedding: Optional[list[float]] = Field(
        None, description="384-dimensional vector embedding"
    )


class ProductRead(ProductBase):
    id: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# RFQ
# ---------------------------------------------------------------------------

class RFQBase(BaseModel):
    buyer_name: str
    cluster_id: str
    target_units: int
    specifications: Optional[str] = None
    offered_unit_price: float
    status: str = Field(
        "PENDING", pattern="^(PENDING|ALLOCATED|DISPATCHED)$"
    )


class RFQCreate(RFQBase):
    pass


class RFQRead(RFQBase):
    id: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Search Trend
# ---------------------------------------------------------------------------

class SearchTrendBase(BaseModel):
    query: str
    craft_category: str
    search_count: int = 0
    region: str


class SearchTrendCreate(SearchTrendBase):
    pass


class SearchTrendRead(SearchTrendBase):
    id: str

    model_config = {"from_attributes": True}


# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  ENDPOINT-SPECIFIC REQUEST / RESPONSE SCHEMAS                           ║
# ╚═══════════════════════════════════════════════════════════════════════════╝

# ---------------------------------------------------------------------------
# POST /api/v1/catalog/ingest
# ---------------------------------------------------------------------------

class PriceRecommendation(BaseModel):
    """Output of the dynamic pricing assistant."""
    cost_floor: float
    recommended_price: float
    min_market_corridor: float
    max_market_corridor: float
    net_artisan_margin: float
    pricing_method: str = Field(
        ..., description="'xgboost' or 'heuristic'"
    )


class CatalogMetadata(BaseModel):
    """Structured fields extracted from the artisan transcript."""
    craft_type: Optional[str] = None
    material: Optional[str] = None
    primary_color: Optional[str] = None
    labor_days: Optional[float] = None
    raw_cost: Optional[float] = None
    title_en: Optional[str] = None
    title_hi: Optional[str] = None
    description_en: Optional[str] = None
    description_hi: Optional[str] = None


class CatalogIngestResponse(BaseModel):
    """Unified response for the catalog ingest pipeline."""
    studio_image_base64: str = Field(
        ..., description="Base64-encoded studio-processed image (WebP)"
    )
    raw_transcript: str
    catalog_metadata: CatalogMetadata
    price_recommendation: PriceRecommendation
    artisan_id: str


# ---------------------------------------------------------------------------
# POST /api/v1/catalog/publish
# ---------------------------------------------------------------------------

class PublishRequest(BaseModel):
    """Approved product metadata submitted for persistence."""
    artisan_id: str
    title_en: str
    title_hi: str
    craft_type: str
    material: str
    raw_cost: float
    labor_days: float
    recommended_price: float
    min_market_corridor: float
    max_market_corridor: float
    raw_image_path: Optional[str] = None
    studio_image_path: Optional[str] = None
    is_active: bool = True
    description_en: Optional[str] = None
    description_hi: Optional[str] = None


class PublishResponse(BaseModel):
    """Confirmation after committing a product record."""
    product_id: str
    title_en: str
    recommended_price: float
    embedding_stored: bool
    message: str


# ---------------------------------------------------------------------------
# GET /api/v1/clusters/map  – GeoJSON
# ---------------------------------------------------------------------------

class ClusterGeoProperties(BaseModel):
    """Properties block inside a GeoJSON Feature."""
    id: str
    name: str
    state: str
    district: str
    primary_craft: str
    combined_monthly_capacity: int
    active_artisan_count: int


class ClusterGeoFeature(BaseModel):
    """A single GeoJSON Feature."""
    type: str = "Feature"
    geometry: dict = Field(
        ..., description='{"type": "Point", "coordinates": [lng, lat]}'
    )
    properties: ClusterGeoProperties


class ClusterGeoJSON(BaseModel):
    """Full GeoJSON FeatureCollection for the clusters map."""
    type: str = "FeatureCollection"
    features: list[ClusterGeoFeature]


# ---------------------------------------------------------------------------
# POST /api/v1/rfq/aggregate
# ---------------------------------------------------------------------------

class RFQAggregateRequest(BaseModel):
    """Buyer RFQ submission."""
    buyer_name: str
    cluster_id: str
    target_units: int
    target_unit_price: float
    custom_specs: Optional[str] = None


class ArtisanAllocation(BaseModel):
    """One artisan's slice of the RFQ allocation."""
    artisan_id: str
    artisan_name: str
    allocated_units: int
    payout_amount: float


class RFQAggregateResponse(BaseModel):
    """Allocation ledger returned after RFQ processing."""
    rfq_id: str
    buyer_name: str
    cluster_id: str
    total_units: int
    unit_price: float
    total_value: float
    status: str
    allocations: list[ArtisanAllocation]


# ---------------------------------------------------------------------------
# GET /api/v1/demand-radar
# ---------------------------------------------------------------------------

class DemandAlert(BaseModel):
    """A single demand notification item."""
    craft_category: str
    region: str
    search_count: int
    pct_change: int
    notification: str


class DemandRadarResponse(BaseModel):
    """Demand radar results for a cluster / dialect."""
    cluster_id: Optional[str] = None
    dialect: str
    alerts: list[DemandAlert]


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login & /api/v1/auth/register
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Phone + PIN login."""
    phone: str = Field(..., description="Phone number with country code, e.g. +919876500001")
    pin: str = Field(..., min_length=4, max_length=6, description="4-6 digit PIN")


class ArtisanProfileResponse(BaseModel):
    """Artisan profile returned after login / from /me endpoint."""
    id: str
    name: str
    phone: str
    cluster_id: str
    cluster_name: str
    dialect: str
    rating: float
    verified: bool


class LoginResponse(BaseModel):
    """JWT token + artisan profile."""
    token: str
    artisan: ArtisanProfileResponse


class RegisterRequest(BaseModel):
    """New artisan registration."""
    name: str = Field(..., min_length=2)
    phone: str = Field(..., description="Phone number with country code")
    pin: str = Field(..., min_length=4, max_length=6)
    cluster_id: str
    dialect: str = Field("hi", max_length=10)
    daily_wage: float = Field(350.0, gt=0)


# ---------------------------------------------------------------------------
# GET /api/v1/artisan/me/dashboard
# ---------------------------------------------------------------------------

class DashboardMetricsResponse(BaseModel):
    """Computed dashboard metrics for an artisan."""
    active_items: int
    total_orders: int
    total_earnings: float


# ---------------------------------------------------------------------------
# GET /api/v1/artisan/me/orders
# ---------------------------------------------------------------------------

class OrderShareResponse(BaseModel):
    """An artisan's allocated share from an RFQ."""
    rfq_id: str
    buyer_name: str
    allocated_units: int
    payout_amount: float
    status: str


# ---------------------------------------------------------------------------
# GET /api/v1/catalog/products
# ---------------------------------------------------------------------------

class CatalogProductResponse(BaseModel):
    """A product with joined artisan and cluster info for the web catalog."""
    id: str
    title_en: str
    title_hi: str
    craft_type: str
    material: str
    raw_cost: float
    labor_days: float
    recommended_price: float
    min_market_corridor: float
    max_market_corridor: float
    studio_image_path: Optional[str] = None
    is_active: bool
    artisan_name: str
    cluster_name: str
    rating: float


class CatalogProductListResponse(BaseModel):
    """List of catalog products."""
    products: list[CatalogProductResponse]
    total: int

// ─── GeoJSON / Cluster Map ───────────────────────────────────────────────────

export interface ClusterGeoProperties {
  id: string;
  name: string;
  state: string;
  district: string;
  primary_craft: string;
  combined_monthly_capacity: number;
  active_artisan_count: number;
}

export interface ClusterGeoFeature {
  type: "Feature";
  geometry: {
    type: "Point";
    coordinates: [number, number]; // [lng, lat]
  };
  properties: ClusterGeoProperties;
}

export interface ClusterGeoJSON {
  type: "FeatureCollection";
  features: ClusterGeoFeature[];
}

// ─── Catalog / Product ───────────────────────────────────────────────────────

export interface ProductCard {
  id: string;
  title_en: string;
  title_hi: string;
  craft_type: string;
  material: string;
  recommended_price: number;
  studio_image_path: string | null;
  artisan_name: string;
  cluster_name: string;
  rating: number;
  labor_days: number;
}

// ─── RFQ ─────────────────────────────────────────────────────────────────────

export interface RFQAggregateRequest {
  buyer_name: string;
  cluster_id: string;
  target_units: number;
  target_unit_price: number;
  custom_specs: string | null;
}

export interface ArtisanAllocation {
  artisan_id: string;
  artisan_name: string;
  allocated_units: number;
  payout_amount: number;
}

export interface RFQAggregateResponse {
  rfq_id: string;
  buyer_name: string;
  cluster_id: string;
  total_units: number;
  unit_price: number;
  total_value: number;
  status: string;
  allocations: ArtisanAllocation[];
}

// ─── Demand Radar ────────────────────────────────────────────────────────────

export interface DemandAlert {
  craft_category: string;
  region: string;
  search_count: number;
  pct_change: number;
  notification: string;
}

export interface DemandRadarResponse {
  cluster_id: string | null;
  dialect: string;
  alerts: DemandAlert[];
}

// ─── Catalog Products ────────────────────────────────────────────────────────

export interface CatalogProduct {
  id: string;
  title_en: string;
  title_hi: string;
  craft_type: string;
  material: string;
  raw_cost: number;
  labor_days: number;
  recommended_price: number;
  min_market_corridor: number;
  max_market_corridor: number;
  studio_image_path: string | null;
  is_active: boolean;
  artisan_name: string;
  cluster_name: string;
  rating: number;
}

export interface CatalogProductListResponse {
  products: CatalogProduct[];
  total: number;
}

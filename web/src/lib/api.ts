import axios from "axios";
import type {
  CatalogProductListResponse,
  ClusterGeoJSON,
  DemandRadarResponse,
  RFQAggregateRequest,
  RFQAggregateResponse,
} from "@/types";

const getBaseUrl = (): string => {
  if (typeof window !== "undefined") {
    // In browser: relative requests use Next.js rewrites proxy, or explicit public URL
    return process.env.NEXT_PUBLIC_API_URL || "";
  }
  // In server runtime (SSR): use internal network URL or fallback
  return (
    process.env.BACKEND_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000"
  );
};

const api = axios.create({
  baseURL: getBaseUrl(),
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

// ─── Clusters ────────────────────────────────────────────────────────────────

export async function fetchClustersGeoJSON(): Promise<ClusterGeoJSON> {
  const { data } = await api.get<ClusterGeoJSON>("/api/v1/clusters/map");
  return data;
}

// ─── Catalog ─────────────────────────────────────────────────────────────────

export async function fetchProducts(): Promise<CatalogProductListResponse> {
  const { data } = await api.get<CatalogProductListResponse>("/api/v1/catalog/products");
  return data;
}

export async function searchCatalog(query: string): Promise<CatalogProductListResponse> {
  const { data } = await api.get<CatalogProductListResponse>(
    "/api/v1/catalog/products/search",
    { params: { q: query } }
  );
  return data;
}

// ─── RFQ ─────────────────────────────────────────────────────────────────────

export async function submitRFQ(
  payload: RFQAggregateRequest
): Promise<RFQAggregateResponse> {
  const { data } = await api.post<RFQAggregateResponse>(
    "/api/v1/rfq/aggregate",
    payload
  );
  return data;
}

// ─── Demand Radar ────────────────────────────────────────────────────────────

export async function fetchDemandRadar(
  dialect: string = "en"
): Promise<DemandRadarResponse> {
  const { data } = await api.get<DemandRadarResponse>(
    "/api/v1/demand-radar",
    { params: { dialect, limit: 10 } }
  );
  return data;
}

export default api;

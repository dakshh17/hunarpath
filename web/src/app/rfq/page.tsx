"use client";

import { useEffect, useState, useMemo, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  ShoppingCart,
  Users,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Package,
  Palette,
  Upload,
  ChevronRight,
} from "lucide-react";
import { fetchClustersGeoJSON, submitRFQ } from "@/lib/api";
import type {
  ClusterGeoFeature,
  RFQAggregateResponse,
  ArtisanAllocation,
} from "@/types";

// ─── Inner page (reads searchParams) ────────────────────────────────────────

function RFQPageInner() {
  const searchParams = useSearchParams();
  const preselectedCluster = searchParams.get("cluster") ?? "";
  const preselectedCraft = searchParams.get("craft") ?? "";

  // Cluster list
  const [clusters, setClusters] = useState<ClusterGeoFeature[]>([]);
  const [loadingClusters, setLoadingClusters] = useState(true);

  // Form state
  const [buyerName, setBuyerName] = useState("");
  const [clusterId, setClusterId] = useState(preselectedCluster);
  const [targetUnits, setTargetUnits] = useState(100);
  const [unitPrice, setUnitPrice] = useState(1500);
  const [customSpecs, setCustomSpecs] = useState(preselectedCraft ? `Craft: ${preselectedCraft}` : "");

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<RFQAggregateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load clusters
  useEffect(() => {
    fetchClustersGeoJSON()
      .then((geo) => {
        setClusters(geo.features);
        if (!clusterId && geo.features.length > 0) {
          setClusterId(geo.features[0].properties.id);
        }
      })
      .catch(() => {})
      .finally(() => setLoadingClusters(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Selected cluster metadata
  const selectedCluster = useMemo(
    () => clusters.find((c) => c.properties.id === clusterId),
    [clusters, clusterId]
  );
  const artisanCount = selectedCluster?.properties.active_artisan_count ?? 0;
  const capacity = selectedCluster?.properties.combined_monthly_capacity ?? 0;

  // Estimated artisans required
  const estimatedArtisans = useMemo(() => {
    if (artisanCount === 0) return 0;
    // Rough heuristic: each artisan handles ~capacity/artisanCount units/month
    const perArtisan = capacity > 0 ? capacity / artisanCount : 20;
    return Math.min(artisanCount, Math.max(1, Math.ceil(targetUnits / perArtisan)));
  }, [artisanCount, capacity, targetUnits]);

  const totalValue = targetUnits * unitPrice;

  const handleSubmit = useCallback(async () => {
    if (!buyerName.trim() || !clusterId) return;

    setSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const res = await submitRFQ({
        buyer_name: buyerName,
        cluster_id: clusterId,
        target_units: targetUnits,
        target_unit_price: unitPrice,
        custom_specs: customSpecs || null,
      });
      setResult(res);
    } catch (err: any) {
      setError(
        err.response?.data?.detail ?? err.message ?? "Submission failed"
      );
    } finally {
      setSubmitting(false);
    }
  }, [buyerName, clusterId, targetUnits, unitPrice, customSpecs]);

  // ── Success view ────────────────────────────────────────────────────
  if (result) {
    return (
      <div className="space-y-8">
        <div className="card-elevated max-w-2xl mx-auto text-center space-y-4">
          <CheckCircle2 className="mx-auto h-16 w-16 text-forest-500" />
          <h2 className="text-2xl font-extrabold text-gray-900">
            Order Allocated Successfully
          </h2>
          <p className="text-gray-500">
            RFQ <span className="font-mono text-sm">{result.rfq_id}</span>{" "}
            has been split across {result.allocations.length} artisans.
          </p>

          <div className="grid grid-cols-3 gap-3 mt-6">
            <div className="rounded-xl bg-gray-50 p-4">
              <p className="text-2xl font-extrabold text-gray-900">
                {result.total_units}
              </p>
              <p className="text-xs text-gray-500">Total Units</p>
            </div>
            <div className="rounded-xl bg-gray-50 p-4">
              <p className="text-2xl font-extrabold text-gray-900">
                ₹{result.unit_price.toLocaleString("en-IN")}
              </p>
              <p className="text-xs text-gray-500">Unit Price</p>
            </div>
            <div className="rounded-xl bg-forest-50 p-4">
              <p className="text-2xl font-extrabold text-forest-600">
                ₹{result.total_value.toLocaleString("en-IN")}
              </p>
              <p className="text-xs text-gray-500">Total Value</p>
            </div>
          </div>
        </div>

        {/* Allocation ledger */}
        <div className="card-elevated max-w-2xl mx-auto">
          <h3 className="text-lg font-bold text-gray-900 mb-4">
            Artisan Allocation Ledger
          </h3>
          <div className="divide-y divide-gray-100">
            {result.allocations.map((a) => (
              <AllocationRow key={a.artisan_id} allocation={a} />
            ))}
          </div>
        </div>

        <div className="flex justify-center">
          <button
            onClick={() => {
              setResult(null);
              setBuyerName("");
              setTargetUnits(100);
            }}
            className="btn-outline"
          >
            Place Another Order
          </button>
        </div>
      </div>
    );
  }

  // ── Form view ───────────────────────────────────────────────────────

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-extrabold text-gray-900">
          Bulk Order Engine
        </h1>
        <p className="mt-1 text-gray-500 text-justify">
          Aggregate micro-artisans seamlessly for enterprise-scale fulfilment
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
        {/* Form */}
        <div className="card-elevated space-y-6">
          {/* Buyer name */}
          <div>
            <label className="mb-1.5 block text-sm font-semibold text-gray-700">
              Buyer / Company Name
            </label>
            <input
              type="text"
              value={buyerName}
              onChange={(e) => setBuyerName(e.target.value)}
              placeholder="e.g. FabIndia Procurement"
              className="input-field"
            />
          </div>

          {/* Cluster picker */}
          <div>
            <label className="mb-1.5 block text-sm font-semibold text-gray-700">
              Source Cluster
            </label>
            {loadingClusters ? (
              <div className="flex items-center gap-2 text-gray-400 py-3">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading clusters...
              </div>
            ) : (
              <select
                value={clusterId}
                onChange={(e) => setClusterId(e.target.value)}
                className="input-field"
              >
                {clusters.map((c) => (
                  <option key={c.properties.id} value={c.properties.id}>
                    {c.properties.name} - {c.properties.primary_craft}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Volume slider */}
          <div>
            <label className="mb-1.5 flex items-center justify-between text-sm font-semibold text-gray-700">
              <span>Order Volume</span>
              <span className="text-xl font-extrabold text-saffron-500">
                {targetUnits.toLocaleString()} units
              </span>
            </label>
            <input
              type="range"
              min={20}
              max={2000}
              step={10}
              value={targetUnits}
              onChange={(e) => setTargetUnits(Number(e.target.value))}
              className="w-full h-3 rounded-full appearance-none bg-gray-200 accent-saffron-500 cursor-pointer"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>20</span>
              <span>500</span>
              <span>1,000</span>
              <span>2,000</span>
            </div>
          </div>

          {/* Unit price */}
          <div>
            <label className="mb-1.5 block text-sm font-semibold text-gray-700">
              Target Unit Price (₹)
            </label>
            <input
              type="number"
              min={100}
              step={50}
              value={unitPrice}
              onChange={(e) => setUnitPrice(Number(e.target.value))}
              className="input-field"
            />
          </div>

          {/* Custom specs */}
          <div>
            <label className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold text-gray-700">
              <Palette className="h-4 w-4" />
              Custom Specifications
            </label>
            <textarea
              value={customSpecs}
              onChange={(e) => setCustomSpecs(e.target.value)}
              rows={3}
              placeholder="Dimensions, colours, branding instructions..."
              className="input-field resize-none"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          <button
            onClick={handleSubmit}
            disabled={submitting || !buyerName.trim() || !clusterId}
            className="btn-forest w-full !py-4 text-lg"
          >
            {submitting ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <ShoppingCart className="h-5 w-5" />
            )}
            {submitting ? "Allocating..." : "Submit Order Request"}
          </button>
        </div>

        {/* Live aggregation summary */}
        <div className="space-y-4">
          <div className="card-elevated space-y-4">
            <h3 className="text-lg font-bold text-gray-900">
              Aggregation Preview
            </h3>

            <div className="flex items-center gap-3 rounded-xl bg-saffron-50 px-4 py-3">
              <Users className="h-8 w-8 text-saffron-500" />
              <div>
                <p className="text-2xl font-extrabold text-gray-900">
                  {estimatedArtisans}
                </p>
                <p className="text-xs text-gray-500">
                  artisans auto-pooled to fulfil {targetUnits} units
                </p>
              </div>
            </div>

            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Cluster Capacity</span>
                <span className="font-semibold">{capacity} units/mo</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Verified Artisans</span>
                <span className="font-semibold">{artisanCount}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Total Value</span>
                <span className="font-extrabold text-forest-600">
                  ₹{totalValue.toLocaleString("en-IN")}
                </span>
              </div>
            </div>
          </div>

          {selectedCluster && (
            <div className="card-elevated">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Selected Cluster
              </p>
              <p className="mt-1 text-base font-bold text-gray-900">
                {selectedCluster.properties.name}
              </p>
              <p className="text-sm text-gray-500">
                {selectedCluster.properties.district},{" "}
                {selectedCluster.properties.state}
              </p>
              <span className="badge mt-2 bg-saffron-50 text-saffron-600">
                {selectedCluster.properties.primary_craft}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Allocation row ──────────────────────────────────────────────────────────

function AllocationRow({ allocation }: { allocation: ArtisanAllocation }) {
  return (
    <div className="flex items-center justify-between py-3">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-forest-50 text-forest-600 font-bold text-sm">
          {allocation.artisan_name.charAt(0)}
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-900">
            {allocation.artisan_name}
          </p>
          <p className="text-xs text-gray-400">
            {allocation.allocated_units} units
          </p>
        </div>
      </div>
      <span className="text-sm font-bold text-forest-600">
        ₹{allocation.payout_amount.toLocaleString("en-IN")}
      </span>
    </div>
  );
}

// ─── Wrapper with Suspense for useSearchParams ───────────────────────────────

export default function RFQPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[40vh] items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-saffron-500" />
        </div>
      }
    >
      <RFQPageInner />
    </Suspense>
  );
}

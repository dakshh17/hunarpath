"use client";

import { useEffect, useState, useMemo } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
  MapPin,
  Users,
  Package,
  ShoppingCart,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { fetchClustersGeoJSON } from "@/lib/api";
import type { ClusterGeoFeature, ClusterGeoJSON } from "@/types";

// Leaflet must be loaded client-side only (no SSR)
const MapContainer = dynamic(
  () => import("react-leaflet").then((m) => m.MapContainer),
  { ssr: false }
);
const TileLayer = dynamic(
  () => import("react-leaflet").then((m) => m.TileLayer),
  { ssr: false }
);
const Marker = dynamic(
  () => import("react-leaflet").then((m) => m.Marker),
  { ssr: false }
);
const Popup = dynamic(
  () => import("react-leaflet").then((m) => m.Popup),
  { ssr: false }
);

// ─── Custom Leaflet icon (avoids missing marker image in Next.js) ────────────

function useLeafletIcon() {
  const [icon, setIcon] = useState<L.Icon | null>(null);

  useEffect(() => {
    import("leaflet").then((L) => {
      setIcon(
        new L.Icon({
          iconUrl:
            "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
          iconRetinaUrl:
            "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
          shadowUrl:
            "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
          iconSize: [25, 41],
          iconAnchor: [12, 41],
          popupAnchor: [1, -34],
        })
      );
    });
  }, []);

  return icon;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ClusterMapPage() {
  const [geoData, setGeoData] = useState<ClusterGeoJSON | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCluster, setSelectedCluster] =
    useState<ClusterGeoFeature | null>(null);

  const markerIcon = useLeafletIcon();

  useEffect(() => {
    fetchClustersGeoJSON()
      .then(setGeoData)
      .catch((err) => setError(err.message ?? "Failed to load clusters"))
      .finally(() => setLoading(false));
  }, []);

  // India-centred default view
  const center: [number, number] = [22.5, 78.5];
  const zoom = 5;

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-saffron-500" />
        <span className="ml-3 text-lg text-gray-600">Loading cluster map...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <p className="text-red-600">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="btn-saffron"
        >
          Retry
        </button>
      </div>
    );
  }

  const features = geoData?.features ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-extrabold text-gray-900">
          Craft Cluster Map
        </h1>
        <p className="mt-1 text-gray-500 text-justify">
          {features.length} verified artisan clusters across India
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        {/* Map */}
        <div className="card-elevated !p-0 overflow-hidden h-[520px] lg:h-[600px]">
          {markerIcon && (
            <MapContainer
              center={center}
              zoom={zoom}
              scrollWheelZoom
              className="h-full w-full rounded-2xl"
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              {features.map((feature) => {
                const [lng, lat] = feature.geometry.coordinates;
                const p = feature.properties;
                return (
                  <Marker
                    key={p.id}
                    position={[lat, lng]}
                    icon={markerIcon}
                    eventHandlers={{
                      click: () => setSelectedCluster(feature),
                    }}
                  >
                    <Popup>
                      <div className="min-w-[200px]">
                        <p className="font-bold text-base">{p.name}</p>
                        <p className="text-sm text-gray-500">
                          {p.district}, {p.state}
                        </p>
                      </div>
                    </Popup>
                  </Marker>
                );
              })}
            </MapContainer>
          )}
        </div>

        {/* Sidebar: selected cluster info */}
        <div className="space-y-4">
          {selectedCluster ? (
            <ClusterInfoCard feature={selectedCluster} />
          ) : (
            <div className="card-elevated text-center text-gray-400 py-16">
              <MapPin className="mx-auto h-12 w-12 mb-4 opacity-30" />
              <p className="text-lg font-medium">Select a cluster on the map</p>
              <p className="text-sm mt-1">
                Click any pin to view cluster details
              </p>
            </div>
          )}

          {/* Quick stats */}
          <div className="grid grid-cols-2 gap-3">
            <StatCard
              icon={<MapPin className="h-5 w-5 text-saffron-500" />}
              value={features.length}
              label="Clusters"
            />
            <StatCard
              icon={<Users className="h-5 w-5 text-forest-500" />}
              value={features.reduce(
                (s, f) => s + f.properties.active_artisan_count,
                0
              )}
              label="Artisans"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Subcomponents ───────────────────────────────────────────────────────────

function ClusterInfoCard({ feature }: { feature: ClusterGeoFeature }) {
  const p = feature.properties;

  return (
    <div className="card-elevated space-y-4">
      <div>
        <h2 className="text-xl font-bold text-gray-900">{p.name}</h2>
        <p className="text-sm text-gray-500">
          {p.district}, {p.state}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <InfoTile
          icon={<Package className="h-4 w-4 text-saffron-500" />}
          label="Primary Craft"
          value={p.primary_craft}
        />
        <InfoTile
          icon={<Users className="h-4 w-4 text-forest-500" />}
          label="Verified Artisans"
          value={String(p.active_artisan_count)}
        />
        <InfoTile
          icon={<ShoppingCart className="h-4 w-4 text-purple-500" />}
          label="Monthly Capacity"
          value={`${p.combined_monthly_capacity} units`}
        />
        <InfoTile
          icon={<MapPin className="h-4 w-4 text-blue-500" />}
          label="Coordinates"
          value={`${feature.geometry.coordinates[1].toFixed(2)}°N`}
        />
      </div>

      <Link
        href={`/rfq?cluster=${p.id}&craft=${encodeURIComponent(p.primary_craft)}`}
        className="btn-forest w-full"
      >
        <ShoppingCart className="h-5 w-5" />
        Source From This Cluster
      </Link>
    </div>
  );
}

function InfoTile({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl bg-gray-50 px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-xs font-medium text-gray-500">
        {icon}
        {label}
      </div>
      <p className="mt-1 text-sm font-bold text-gray-900">{value}</p>
    </div>
  );
}

function StatCard({
  icon,
  value,
  label,
}: {
  icon: React.ReactNode;
  value: number;
  label: string;
}) {
  return (
    <div className="card-elevated flex items-center gap-3 !p-4">
      {icon}
      <div>
        <p className="text-xl font-extrabold text-gray-900">{value}</p>
        <p className="text-xs text-gray-500">{label}</p>
      </div>
    </div>
  );
}

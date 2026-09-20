"use client";

import { useEffect, useState } from "react";
import {
  TrendingUp,
  BarChart3,
  MapPin,
  Flame,
  Loader2,
  AlertCircle,
  ArrowUpRight,
} from "lucide-react";
import { fetchDemandRadar } from "@/lib/api";
import type { DemandAlert } from "@/types";

// ─── Colour mapping for craft categories ─────────────────────────────────────

const CRAFT_COLORS: Record<string, { bg: string; text: string; bar: string }> = {
  "Zari & Brocade": { bg: "bg-amber-50", text: "text-amber-700", bar: "bg-amber-400" },
  "Bell Metal Craft": { bg: "bg-orange-50", text: "text-orange-700", bar: "bg-orange-400" },
  Embroidery: { bg: "bg-pink-50", text: "text-pink-700", bar: "bg-pink-400" },
  "Block Printing": { bg: "bg-indigo-50", text: "text-indigo-700", bar: "bg-indigo-400" },
  "Handloom Weaving": { bg: "bg-teal-50", text: "text-teal-700", bar: "bg-teal-400" },
  "Mirror Work": { bg: "bg-purple-50", text: "text-purple-700", bar: "bg-purple-400" },
  Meenakari: { bg: "bg-emerald-50", text: "text-emerald-700", bar: "bg-emerald-400" },
  "Wood Carving": { bg: "bg-yellow-50", text: "text-yellow-700", bar: "bg-yellow-600" },
  "Wrought Iron": { bg: "bg-slate-100", text: "text-slate-700", bar: "bg-slate-400" },
  Terracotta: { bg: "bg-red-50", text: "text-red-700", bar: "bg-red-400" },
};

const DEFAULT_COLORS = { bg: "bg-gray-50", text: "text-gray-700", bar: "bg-gray-400" };

function craftColor(category: string) {
  return CRAFT_COLORS[category] ?? DEFAULT_COLORS;
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function DemandRadarPage() {
  const [alerts, setAlerts] = useState<DemandAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDemandRadar("en")
      .then((data) => setAlerts(data.alerts))
      .catch((err) =>
        setError(err.message ?? "Failed to load demand data")
      )
      .finally(() => setLoading(false));
  }, []);

  const maxSearchCount = Math.max(...alerts.map((a) => a.search_count), 1);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-saffron-500" />
        <span className="ml-3 text-lg text-gray-600">
          Loading demand radar...
        </span>
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

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-extrabold text-gray-900">
          Demand Radar
        </h1>
        <p className="mt-1 text-gray-500 text-justify">
          Real-time buyer search trends and regional demand signals
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <SummaryCard
          icon={<TrendingUp className="h-6 w-6 text-saffron-500" />}
          title="Active Trends"
          value={alerts.length}
          subtitle="craft categories trending"
          bg="bg-saffron-50"
        />
        <SummaryCard
          icon={<BarChart3 className="h-6 w-6 text-forest-500" />}
          title="Total Searches"
          value={alerts.reduce((s, a) => s + a.search_count, 0)}
          subtitle="aggregate search volume"
          bg="bg-forest-50"
        />
        <SummaryCard
          icon={<Flame className="h-6 w-6 text-red-500" />}
          title="Peak Demand"
          value={`${Math.max(...alerts.map((a) => a.pct_change), 0)}%`}
          subtitle="highest growth spike"
          bg="bg-red-50"
        />
      </div>

      {/* Trend bars + detail cards */}
      <div className="grid gap-8 lg:grid-cols-[1fr_380px]">
        {/* Bar chart section */}
        <div className="card-elevated">
          <h2 className="text-lg font-bold text-gray-900 mb-6">
            Search Volume by Craft Category
          </h2>
          <div className="space-y-4">
            {alerts
              .sort((a, b) => b.search_count - a.search_count)
              .map((alert) => {
                const pct = (alert.search_count / maxSearchCount) * 100;
                const colors = craftColor(alert.craft_category);
                return (
                  <div key={alert.craft_category}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-sm font-semibold text-gray-700">
                        {alert.craft_category}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-gray-900">
                          {alert.search_count.toLocaleString()}
                        </span>
                        <span
                          className={`badge ${colors.bg} ${colors.text}`}
                        >
                          <ArrowUpRight className="h-3 w-3" />
                          {alert.pct_change}%
                        </span>
                      </div>
                    </div>
                    <div className="h-4 w-full overflow-hidden rounded-full bg-gray-100">
                      <div
                        className={`h-full rounded-full ${colors.bar} transition-all duration-700`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
          </div>
        </div>

        {/* Regional detail cards */}
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-gray-900">
            Regional Highlights
          </h2>
          {alerts.map((alert) => {
            const colors = craftColor(alert.craft_category);
            return (
              <div
                key={`${alert.craft_category}-${alert.region}`}
                className="card-elevated !p-4"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <span className={`badge ${colors.bg} ${colors.text} mb-2`}>
                      {alert.craft_category}
                    </span>
                    <div className="flex items-center gap-1.5 text-sm text-gray-500 mt-1">
                      <MapPin className="h-3.5 w-3.5" />
                      {alert.region}
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-xl font-extrabold text-gray-900">
                      +{alert.pct_change}%
                    </p>
                    <p className="text-xs text-gray-400">growth</p>
                  </div>
                </div>
                <div className="mt-3 rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-600 leading-relaxed text-justify">
                  {alert.notification}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ─── Summary card ────────────────────────────────────────────────────────────

function SummaryCard({
  icon,
  title,
  value,
  subtitle,
  bg,
}: {
  icon: React.ReactNode;
  title: string;
  value: number | string;
  subtitle: string;
  bg: string;
}) {
  return (
    <div className="card-elevated flex items-center gap-4">
      <div
        className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${bg}`}
      >
        {icon}
      </div>
      <div>
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          {title}
        </p>
        <p className="text-2xl font-extrabold text-gray-900">
          {typeof value === "number" ? value.toLocaleString() : value}
        </p>
        <p className="text-xs text-gray-500">{subtitle}</p>
      </div>
    </div>
  );
}

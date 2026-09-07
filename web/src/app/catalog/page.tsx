"use client";

import { useState, useCallback, useEffect } from "react";
import {
  Search,
  Star,
  MapPin,
  Clock,
  Loader2,
  Sparkles,
  ImageOff,
} from "lucide-react";
import { fetchProducts, searchCatalog } from "@/lib/api";
import type { CatalogProduct } from "@/types";

// ─── Craft type to emoji mapping ─────────────────────────────────────────────

const CRAFT_EMOJI: Record<string, string> = {
  "Zari & Brocade": "🪡",
  "Handloom Weaving": "🧣",
  "Bell Metal Craft": "🐘",
  Embroidery: "🪷",
  "Block Printing": "🎨",
  "Mirror Work": "👝",
  "Wood Carving": "🪵",
  Meenakari: "💎",
  "Wrought Iron": "⚒️",
  Terracotta: "🪔",
};

function craftEmoji(craftType: string): string {
  return CRAFT_EMOJI[craftType] ?? "🎨";
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function CatalogPage() {
  const [query, setQuery] = useState("");
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load products on mount
  useEffect(() => {
    fetchProducts()
      .then((data) => setProducts(data.products))
      .catch((err) => setError(err.message ?? "Failed to load products"))
      .finally(() => setLoading(false));
  }, []);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) {
      // Reset to full product list
      setSearching(true);
      try {
        const data = await fetchProducts();
        setProducts(data.products);
        setHasSearched(false);
      } catch (err: any) {
        setError(err.message ?? "Failed to load products");
      } finally {
        setSearching(false);
      }
      return;
    }

    setSearching(true);
    setHasSearched(true);

    try {
      const data = await searchCatalog(query);
      setProducts(data.products);
    } catch {
      // On error, keep current products
    } finally {
      setSearching(false);
    }
  }, [query]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-saffron-500" />
        <span className="ml-3 text-lg text-gray-600">Loading catalog…</span>
      </div>
    );
  }

  if (error && products.length === 0) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4">
        <ImageOff className="h-12 w-12 text-red-500" />
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
          Product Catalog
        </h1>
        <p className="mt-1 text-gray-500">
          Search across verified artisan products
        </p>
      </div>

      {/* Search bar */}
      <div className="relative">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder='Try "silk saree" or "bell metal"'
              className="input-field !pl-12 !py-4 text-lg"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={searching}
            className="btn-saffron px-8"
          >
            {searching ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Sparkles className="h-5 w-5" />
            )}
            Search
          </button>
        </div>
        {hasSearched && (
          <p className="mt-2 text-sm text-gray-500">
            Showing {products.length} results for &quot;{query}&quot;
          </p>
        )}
      </div>

      {/* Product grid */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {products.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>

      {products.length === 0 && (
        <div className="py-20 text-center">
          <ImageOff className="mx-auto h-16 w-16 text-gray-300" />
          <p className="mt-4 text-lg font-medium text-gray-500">
            No products found
          </p>
          <p className="mt-1 text-sm text-gray-400">
            {hasSearched
              ? "Try different keywords or browse all products"
              : "Products will appear here once artisans publish them"}
          </p>
        </div>
      )}
    </div>
  );
}

// ─── Product Card ────────────────────────────────────────────────────────────

function ProductCard({ product }: { product: CatalogProduct }) {
  return (
    <div className="card-elevated group flex flex-col transition hover:shadow-lg hover:-translate-y-0.5">
      {/* Image placeholder */}
      <div className="relative flex h-48 items-center justify-center rounded-xl bg-gradient-to-br from-gray-50 to-gray-100">
        <span className="text-6xl">{craftEmoji(product.craft_type)}</span>
        <span className="badge absolute right-2 top-2 bg-saffron-50 text-saffron-600">
          {product.craft_type}
        </span>
      </div>

      {/* Body */}
      <div className="mt-4 flex flex-1 flex-col">
        <h3 className="text-base font-bold text-gray-900 group-hover:text-saffron-500 transition line-clamp-2">
          {product.title_en}
        </h3>

        <p className="mt-1 text-sm text-gray-500">{product.material}</p>

        {/* Artisan & cluster */}
        <div className="mt-3 flex items-center gap-2 text-sm text-gray-600">
          <span className="font-medium">{product.artisan_name}</span>
        </div>
        <div className="flex items-center gap-1 text-xs text-gray-400 mt-0.5">
          <MapPin className="h-3 w-3" />
          {product.cluster_name}
        </div>

        {/* Bottom row: rating, lead time, price */}
        <div className="mt-auto flex items-end justify-between pt-4">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1 text-sm font-medium text-amber-600">
              <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
              {product.rating}
            </span>
            <span className="flex items-center gap-1 text-xs text-gray-400">
              <Clock className="h-3.5 w-3.5" />
              {product.labor_days}d
            </span>
          </div>
          <span className="text-xl font-extrabold text-gray-900">
            ₹{product.recommended_price.toLocaleString("en-IN")}
          </span>
        </div>
      </div>
    </div>
  );
}

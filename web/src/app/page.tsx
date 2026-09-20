import Link from "next/link";
import { Map, Search, ShoppingCart, TrendingUp } from "lucide-react";

const CARDS = [
  {
    href: "/map",
    icon: Map,
    title: "Clusters Map",
    desc: "Explore artisan clusters across India on an interactive map.",
    color: "text-saffron-500",
    bg: "bg-saffron-50",
  },
  {
    href: "/catalog",
    icon: Search,
    title: "Catalog Search",
    desc: "Semantic search across thousands of handcrafted products.",
    color: "text-forest-500",
    bg: "bg-forest-50",
  },
  {
    href: "/rfq",
    icon: ShoppingCart,
    title: "Bulk Order",
    desc: "Aggregate micro-artisans for enterprise-scale fulfillment.",
    color: "text-purple-600",
    bg: "bg-purple-50",
  },
  {
    href: "/demand-radar",
    icon: TrendingUp,
    title: "Demand Radar",
    desc: "Real-time buyer search trends and regional demand heat.",
    color: "text-blue-600",
    bg: "bg-blue-50",
  },
] as const;

export default function HomePage() {
  return (
    <div className="py-12">
      {/* Hero */}
      <div className="text-center">
        <h1 className="text-4xl font-extrabold tracking-tight text-gray-900 sm:text-5xl">
          Hunar<span className="text-saffron-500">Path</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-gray-600 text-justify">
          India&apos;s AI-powered bridge between heritage artisan clusters and
          global buyers. Fair pricing, transparent supply chains, zero
          middlemen.
        </p>
      </div>

      {/* Feature cards */}
      <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {CARDS.map(({ href, icon: Icon, title, desc, color, bg }) => (
          <Link
            key={href}
            href={href}
            className="card-elevated group transition hover:shadow-lg hover:-translate-y-1"
          >
            <div
              className={`mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl ${bg}`}
            >
              <Icon className={`h-6 w-6 ${color}`} />
            </div>
            <h2 className="text-lg font-bold text-gray-900 group-hover:text-saffron-500 transition">
              {title}
            </h2>
            <p className="mt-2 text-sm text-gray-500 text-justify">{desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}

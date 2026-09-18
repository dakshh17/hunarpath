"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Map,
  Search,
  ShoppingCart,
  TrendingUp,
  Hexagon,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/map", label: "Clusters Map", icon: Map },
  { href: "/catalog", label: "Catalog", icon: Search },
  { href: "/rfq", label: "Bulk Order", icon: ShoppingCart },
  { href: "/demand-radar", label: "Demand Radar", icon: TrendingUp },
] as const;

export default function Navbar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-gray-200 bg-white/80 backdrop-blur-lg">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        {/* Brand */}
        <Link href="/" className="flex items-center gap-2">
          <Hexagon className="h-8 w-8 text-saffron-500" strokeWidth={2.5} />
          <span className="text-xl font-bold text-gray-900">
            Hunar<span className="text-saffron-500">Path</span>
          </span>
        </Link>

        {/* Nav links */}
        <nav className="hidden items-center gap-1 md:flex">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition
                  ${
                    active
                      ? "bg-saffron-50 text-saffron-600"
                      : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                  }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Mobile menu (simplified) */}
        <nav className="flex items-center gap-3 md:hidden">
          {NAV_ITEMS.map(({ href, icon: Icon }) => {
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`rounded-lg p-2 transition ${
                  active
                    ? "bg-saffron-50 text-saffron-600"
                    : "text-gray-500 hover:text-gray-900"
                }`}
              >
                <Icon className="h-5 w-5" />
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}

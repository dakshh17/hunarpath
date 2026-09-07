import type { Metadata } from "next";
import Navbar from "@/components/Navbar";
import "./globals.css";

export const metadata: Metadata = {
  title: "ShilpSetu — Artisan Marketplace",
  description:
    "Enterprise & retail buyer marketplace connecting businesses with verified Indian artisan clusters for bulk craft sourcing.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans">
        <Navbar />
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
          {children}
        </main>
      </body>
    </html>
  );
}

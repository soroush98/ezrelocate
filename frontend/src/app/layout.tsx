import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "EZrelocate · Canadian rentals",
  description:
    "AI-powered rental search across Canada — hybrid PostGIS + pgvector + Claude.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="h-screen overflow-hidden">{children}</body>
    </html>
  );
}

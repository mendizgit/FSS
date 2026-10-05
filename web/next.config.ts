import type { NextConfig } from "next";

// In production Caddy routes /api and /ws to the api service before they reach Next.
// For local development set API_ORIGIN (e.g. http://127.0.0.1:8000) to proxy /api.
const apiOrigin = process.env.API_ORIGIN;

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return apiOrigin ? [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }] : [];
  },
};

export default nextConfig;

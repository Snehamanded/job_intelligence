import type { NextConfig } from "next";

// In production the browser talks only to this site: /api/* is proxied to the API (API_ORIGIN,
// e.g. https://jobcrm-api.onrender.com), so the login cookie is first-party and SameSite=Lax holds.
const apiOrigin = process.env.API_ORIGIN?.replace(/\/+$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return apiOrigin ? [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }] : [];
  },
};

export default nextConfig;

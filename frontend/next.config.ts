import type { NextConfig } from "next";

/**
 * Same-origin proxy to the FastAPI backend.
 *
 * The browser was calling the Render backend cross-origin, which (a) tripped
 * privacy/content blockers that abort the request before it leaves the machine
 * (`net::ERR_BLOCKED_BY_CLIENT`) and (b) required CORS. Routing REST + /health
 * through a first-party rewrite (`/api/backend/*` -> backend origin) makes every
 * fetch same-origin: blockers leave it alone and CORS no longer applies. The
 * live-events WebSocket can't be proxied here and still connects directly.
 */
const BACKEND_ORIGIN = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${BACKEND_ORIGIN}/:path*`,
      },
    ];
  },
};

export default nextConfig;

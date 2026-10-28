import type { NextConfig } from "next";

// The browser only talks to this app. Requests to /api are forwarded to the FastAPI service,
// so there's no CORS to configure and the API can stay on a private network.
const apiUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8086";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;

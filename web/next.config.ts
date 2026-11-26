import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  basePath: "/compliance", // also BASE in src/lib/api.ts
  poweredByHeader: false,
  // In development the API runs on its own (uvicorn on :8000); in production nginx routes /compliance/api/ to it.
  async rewrites() {
    return process.env.NODE_ENV === "development"
      ? [{ source: "/api/:path*", destination: "http://localhost:8000/api/:path*" }]
      : [];
  },
  // Tailwind v4 via its Turbopack loader, as in Carton Connect (no postcss config).
  turbopack: {
    rules: { "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" } },
  },
};

export default nextConfig;

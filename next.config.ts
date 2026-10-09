import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  turbopack: {
    root: path.resolve(__dirname),
  },
  // Old dashboard URLs, kept working after their pages were merged (Batch E).
  // Exact paths only, so /dashboard/patient and /dashboard/doctor are not affected.
  async redirects() {
    return [
      { source: "/dashboard", destination: "/dashboard/patient", permanent: false },
      { source: "/doctor-dashboard", destination: "/dashboard/doctor", permanent: false },
    ];
  },
};

export default nextConfig;

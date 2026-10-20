import type { NextConfig } from "next";
import path from "node:path";

// Headers every page and API answer carries. The CSP here is the part that cannot break Next.js (it needs inline
// scripts, so script-src is not restricted): it stops the site being framed, a <base> or <form> being pointed at
// another site, and plugins. Camera and microphone are off; the location is only for this site (home visits).
const SECURITY_HEADERS = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(self), payment=()" },
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'" },
  // Only over HTTPS (Render): the browser then refuses plain http for this site for a year.
  ...(process.env.NODE_ENV === "production" ? [{ key: "Strict-Transport-Security", value: "max-age=31536000" }] : []),
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  turbopack: {
    root: path.resolve(__dirname),
  },
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
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

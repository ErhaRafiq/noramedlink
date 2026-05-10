import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  turbopack: {
    root: path.resolve(__dirname),
  },
  serverExternalPackages: ["sharp", "tesseract.js", "mammoth", "pdf-parse"],
};

export default nextConfig;

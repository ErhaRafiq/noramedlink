import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Nora MedLink",
    short_name: "Nora MedLink",
    description: "Patient records, OCR report summaries, appointments and medicine reminders in one place.",
    start_url: "/",
    display: "standalone",
    background_color: "#F4FAFF",
    theme_color: "#2563EB",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}

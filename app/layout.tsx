import type { Metadata, Viewport } from "next";
import { Poppins } from "next/font/google";
import "./globals.css";
import { NotificationsProvider } from "@/components/notifications/NotificationsProvider";

// Poppins is not a variable font, so each weight is listed. 400 body, 500 labels,
// 600 headings and buttons, 700 for the few places that need extra emphasis.
const poppins = Poppins({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
  variable: "--font-poppins",
});

export const metadata: Metadata = {
  title: {
    default: "Nora MedLink",
    template: "%s · Nora MedLink",
  },
  description:
    "Patient records, OCR report summaries, appointments and medicine reminders in one place. An academic prototype; advisory only.",
  applicationName: "Nora MedLink",
};

export const viewport: Viewport = {
  themeColor: "#2563EB",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${poppins.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <NotificationsProvider>{children}</NotificationsProvider>
      </body>
    </html>
  );
}

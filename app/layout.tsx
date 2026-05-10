import type { Metadata } from "next";
import "./globals.css";
import { CursorGlow } from "@/components/ui/CursorGlow";

export const metadata: Metadata = {
  title: "Nora MedLink",
  description: "AI-powered medical intelligence for connected patient and doctor workflows.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <CursorGlow />
        {children}
      </body>
    </html>
  );
}

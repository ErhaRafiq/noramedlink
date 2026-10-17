import type { ReactNode } from "react";

import { LandingFooter } from "@/components/landing/LandingFooter";
import { SiteHeader, type SiteLink } from "./SiteHeader";

/** Header + content + footer frame for the pages outside the dashboards. */
export function SitePage({ children, links, publicView = false }: { children: ReactNode; links?: SiteLink[]; publicView?: boolean }) {
  return (
    <div className="flex min-h-screen flex-col bg-surface-page">
      <SiteHeader links={links} publicView={publicView} />
      <main className="flex-1">{children}</main>
      <LandingFooter />
    </div>
  );
}

import type { Metadata } from "next";
import { Compass } from "lucide-react";

import { SitePage } from "@/components/layout/SitePage";
import { ButtonLink } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Page not found",
};

export default function NotFound() {
  return (
    <SitePage publicView>
      <div className="mx-auto flex max-w-md flex-col items-center px-4 py-24 text-center">
        <span className="grid h-12 w-12 place-items-center rounded-full bg-blue-50 text-brand-blue">
          <Compass className="h-6 w-6" aria-hidden />
        </span>
        <h1 className="mt-5 text-2xl font-semibold text-ink">Page not found</h1>
        <p className="mt-2 text-sm leading-6 text-ink-muted">The page you are looking for does not exist or has moved.</p>
        <div className="mt-6 flex gap-3">
          <ButtonLink href="/">Go home</ButtonLink>
          <ButtonLink href="/doctors" variant="secondary">
            Find a doctor
          </ButtonLink>
        </div>
      </div>
    </SitePage>
  );
}

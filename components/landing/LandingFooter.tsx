import Link from "next/link";

import { NoraLogo } from "@/components/ui/NoraLogo";

export function LandingFooter() {
  return (
    <footer className="border-t border-line bg-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:px-6 md:flex-row md:items-center md:justify-between">
        <div>
          <NoraLogo />
          <p className="mt-3 text-xs leading-5 text-ink-muted">
            Final-year project, BS Data Science, COMSATS University Islamabad. Advisory only.
          </p>
        </div>
        <nav aria-label="Footer">
          <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-600">
            <li>
              <Link href="/about" className="hover:text-ink">
                About
              </Link>
            </li>
            <li>
              <Link href="/doctors" className="hover:text-ink">
                Find a doctor
              </Link>
            </li>
            <li>
              <Link href="/login" className="hover:text-ink">
                Sign in
              </Link>
            </li>
            <li>
              <Link href="/signup?role=patient" className="hover:text-ink">
                Create account
              </Link>
            </li>
          </ul>
        </nav>
      </div>
    </footer>
  );
}

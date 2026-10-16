"use client";

import { Star } from "lucide-react";

import { cn } from "@/lib/cn";

/** A rating shown as stars with its number; `null` means nobody has rated yet. */
export function RatingSummary({ rating, count, className }: { rating: number | null; count: number; className?: string }) {
  if (rating === null) return <span className={cn("block text-sm text-ink-muted", className)}>No ratings yet</span>;
  return (
    <span className={cn("flex items-center gap-1.5 text-sm text-ink-muted", className)}>
      <Star className="h-4 w-4 fill-amber-400 text-amber-400" aria-hidden />
      <span className="font-semibold text-ink">{rating.toFixed(1)}</span>
      <span>
        ({count} {count === 1 ? "rating" : "ratings"})
      </span>
    </span>
  );
}

/** Pick 1 to 5 stars (a radio group, so it works with a keyboard and a screen reader). */
export function StarInput({ value, onChange, disabled }: { value: number; onChange: (value: number) => void; disabled?: boolean }) {
  return (
    <div role="radiogroup" aria-label="Rating" className="flex gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <label key={n} className={cn("cursor-pointer rounded-control p-1 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-blue", disabled && "cursor-not-allowed opacity-60")}>
          <input type="radio" name="rating" value={n} checked={value === n} onChange={() => onChange(n)} disabled={disabled} className="sr-only" />
          <Star className={cn("h-8 w-8 transition-colors", n <= value ? "fill-amber-400 text-amber-400" : "text-slate-300")} aria-hidden />
          <span className="sr-only">{n} out of 5</span>
        </label>
      ))}
    </div>
  );
}

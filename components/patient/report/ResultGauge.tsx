import type { ExplainGauge, ExplainPosition } from "@/lib/types";

const MARKER: Record<ExplainPosition, string> = {
  above: "bg-amber-500",
  below: "bg-amber-500",
  within: "bg-emerald-600",
  unknown: "bg-slate-400",
  unreadable: "bg-slate-400",
};

/** Where a result sits against the usual range: the green band is the range, the dot is the result.
 * The words next to it say the same thing, so the picture is never the only source. */
export function ResultGauge({ gauge, position, label }: { gauge: ExplainGauge; position: ExplainPosition; label: string }) {
  const span = gauge.max - gauge.min || 1;
  const at = (n: number) => Math.min(100, Math.max(0, ((n - gauge.min) / span) * 100));
  const from = gauge.low === null ? 0 : at(gauge.low);
  const to = gauge.high === null ? 100 : at(gauge.high);
  return (
    <div role="img" aria-label={label} className="relative mt-3 h-6">
      <div className="absolute inset-x-0 top-2.5 h-1.5 rounded-full bg-slate-200" />
      <div className="absolute top-2.5 h-1.5 rounded-full bg-emerald-300" style={{ left: `${from}%`, width: `${Math.max(to - from, 1)}%` }} />
      <div
        className={`absolute top-1 h-4 w-4 -translate-x-1/2 rounded-full border-2 border-white shadow ${MARKER[position]}`}
        style={{ left: `${at(gauge.value)}%` }}
      />
    </div>
  );
}

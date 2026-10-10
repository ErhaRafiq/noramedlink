/** Soft brand-tinted backdrop for the public pages. Decorative only. */
export function AmbientBackground() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="ambient-glow" />
      <div className="ambient-grid" />
    </div>
  );
}

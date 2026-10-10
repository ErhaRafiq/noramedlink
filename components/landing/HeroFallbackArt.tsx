/**
 * Still version of the hero scene: shown while the 3D scene loads, and instead of it when
 * WebGL is unavailable. Pure SVG, so it costs nothing to render on the server.
 */
export function HeroFallbackArt() {
  const dots = Array.from({ length: 36 }, (_, i) => {
    const angle = (i / 36) * Math.PI * 2;
    const ring = i % 2 === 0 ? 150 : 118;
    return { x: 200 + Math.cos(angle) * ring, y: 200 + Math.sin(angle) * ring, r: i % 3 === 0 ? 3.2 : 2.2 };
  });

  return (
    <svg viewBox="0 0 400 400" className="h-full w-full" aria-hidden>
      <defs>
        <linearGradient id="hero-fallback-gradient" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2563EB" />
          <stop offset="1" stopColor="#00BFA6" />
        </linearGradient>
      </defs>
      <circle cx="200" cy="200" r="150" fill="none" stroke="#2563EB" strokeOpacity="0.12" />
      <circle cx="200" cy="200" r="118" fill="none" stroke="#00BFA6" strokeOpacity="0.14" />
      <circle cx="200" cy="200" r="78" fill="none" stroke="#00BFA6" strokeOpacity="0.18" />
      {dots.map((dot, i) => (
        <circle key={i} cx={dot.x} cy={dot.y} r={dot.r} fill="url(#hero-fallback-gradient)" opacity="0.7" />
      ))}
      <rect x="182" y="150" width="36" height="100" rx="18" fill="url(#hero-fallback-gradient)" />
      <rect x="150" y="182" width="100" height="36" rx="18" fill="url(#hero-fallback-gradient)" />
    </svg>
  );
}

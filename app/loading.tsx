export default function Loading() {
  return (
    <main className="premium-page grid min-h-screen place-items-center px-6">
      <div className="ambient-glow" aria-hidden="true" />
      <div className="landing-glass w-full max-w-md rounded-[24px] p-6">
        <div className="soft-shimmer h-4 w-28 rounded-full bg-white/10" />
        <div className="soft-shimmer mt-6 h-10 w-full rounded-2xl bg-white/10" />
        <div className="soft-shimmer mt-3 h-10 w-4/5 rounded-2xl bg-white/10" />
        <div className="mt-6 grid gap-3">
          <div className="soft-shimmer h-16 rounded-2xl bg-white/10" />
          <div className="soft-shimmer h-16 rounded-2xl bg-white/10" />
        </div>
      </div>
    </main>
  );
}

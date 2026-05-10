import Link from "next/link";

export function NoraLogo({ inverse = false }: { inverse?: boolean }) {
  return (
    <Link href="/" className="flex items-center gap-3" aria-label="Nora MedLink home">
      <span className={`relative flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-[#2563EB] to-[#00BFA6] ${inverse ? "shadow-lg shadow-teal-950/20" : "shadow-lg shadow-teal-100"}`}>
        <span className="absolute h-7 w-2.5 rounded-full bg-white" />
        <span className="absolute h-2.5 w-7 rounded-full bg-white" />
      </span>
      <span>
        <span className={`block text-lg font-black tracking-tight ${inverse ? "text-white" : "text-[#0B1220]"}`}>
          Nora MedLink
        </span>
        <span className={`block text-[10px] font-bold uppercase tracking-[0.18em] ${inverse ? "text-teal-100" : "text-teal-700"}`}>
          Patient records hub
        </span>
      </span>
    </Link>
  );
}

import { ShieldCheck, Stethoscope, UserRound, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";
import type { UserRole } from "@/lib/types";

const ROLES: Array<{ role: UserRole; title: string; description: string; icon: LucideIcon }> = [
  { role: "patient", title: "Patient", description: "Keep your reports, vitals and medicines", icon: UserRound },
  { role: "doctor", title: "Doctor", description: "Review files patients share with you", icon: Stethoscope },
  { role: "admin", title: "Admin", description: "Requires an invite code", icon: ShieldCheck },
];

/** Account type chooser, built as a radio group so it works with the keyboard. */
export function RoleSelector({ value, onChange }: { value: UserRole; onChange: (role: UserRole) => void }) {
  return (
    <fieldset>
      <legend className="text-sm font-medium text-slate-700">Account type</legend>
      <div className="mt-2 grid gap-3 sm:grid-cols-3">
        {ROLES.map(({ role, title, description, icon: Icon }) => {
          const selected = value === role;
          return (
            <label
              key={role}
              className={cn(
                "flex cursor-pointer items-center gap-3 rounded-card border p-3 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-blue sm:flex-col sm:items-start sm:gap-2 sm:p-4",
                selected ? "border-brand-blue bg-blue-50/60" : "border-line bg-white hover:border-line-strong",
              )}
            >
              <input type="radio" name="role" value={role} checked={selected} onChange={() => onChange(role)} className="sr-only" />
              <span className={cn("grid h-9 w-9 place-items-center rounded-control", selected ? "bg-brand-blue text-white" : "bg-surface-soft text-ink-muted")}>
                <Icon className="h-4 w-4" aria-hidden />
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-ink">{title}</span>
                <span className="block text-xs leading-5 text-ink-muted">{description}</span>
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

import Link from "next/link";
import { CalendarDays, CreditCard, FileText, Pill, type LucideIcon } from "lucide-react";

import { Card, CardHeader } from "@/components/ui/card";
import type { Profile } from "@/lib/types";

type Item = { label: string; value: number; href: string; icon: LucideIcon };

/** What is linked to this profile (reports, appointments, prescriptions, payments), each opening its own page. */
export function Activity({ profile }: { profile: Profile }) {
  const { activity } = profile;
  const patient = profile.patient !== null;
  const home = patient ? "/dashboard/patient" : "/dashboard/doctor";
  const items: Item[] = patient
    ? [
        { label: "Reports", value: activity.reports, href: `${home}#reports`, icon: FileText },
        { label: "Appointments", value: activity.appointments, href: `${home}#appointments`, icon: CalendarDays },
        { label: "Prescriptions", value: activity.prescriptions, href: `${home}#prescriptions`, icon: Pill },
        { label: "Payments", value: activity.payments, href: "/payments", icon: CreditCard },
      ]
    : [
        { label: "Appointments", value: activity.appointments, href: `${home}#appointments`, icon: CalendarDays },
        { label: "Prescriptions written", value: activity.prescriptions, href: `${home}#prescribe`, icon: Pill },
        { label: "Payments received", value: activity.payments, href: home, icon: CreditCard },
      ];
  if (profile.account.role === "admin") return null;
  return (
    <Card aria-labelledby="activity-title">
      <CardHeader title={<span id="activity-title">Linked to your profile</span>} description="Your records, appointments, prescriptions and payments are all kept under this one profile." />
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {items.map((item) => (
          <li key={item.label}>
            <Link href={item.href} className="floating-card flex items-center gap-3 rounded-control border border-line p-3.5 hover:border-line-strong">
              <span className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-control bg-blue-50 text-brand-blue">
                <item.icon className="h-4 w-4" aria-hidden />
              </span>
              <span className="min-w-0">
                <span className="block text-xl font-semibold leading-6 text-ink">{item.value}</span>
                <span className="block truncate text-xs text-ink-muted">{item.label}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

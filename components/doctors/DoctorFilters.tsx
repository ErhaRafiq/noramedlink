import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ALL_SPECIALTIES, type useDoctorDirectory } from "@/hooks/doctors/use-doctor-directory";
import type { ConsultationMode, DoctorSort } from "@/lib/types";

type Directory = ReturnType<typeof useDoctorDirectory>;

const SORTS: Array<[DoctorSort, string]> = [
  ["soonest", "Soonest available"],
  ["rating", "Highest rated"],
  ["fee", "Lowest fee"],
  ["experience", "Most experienced"],
  ["name", "Name"],
];

export function DoctorFilters({ directory }: { directory: Directory }) {
  const { filters, specialties } = directory;
  return (
    <section aria-label="Find a doctor" className="space-y-3 rounded-card border border-line bg-white p-4 shadow-card">
      <div className="grid gap-3 sm:grid-cols-[1fr_220px]">
        <label className="relative block">
          <span className="sr-only">Search doctors</span>
          <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
          <input
            type="search"
            value={filters.search}
            onChange={(event) => filters.setSearch(event.target.value)}
            placeholder="Search by name, specialty, hospital or qualification"
            className="form-field pl-10"
          />
        </label>
        <label className="block">
          <span className="sr-only">Specialty</span>
          <select value={filters.specialty} onChange={(event) => filters.setSpecialty(event.target.value)} className="form-field">
            <option value={ALL_SPECIALTIES}>All specialties</option>
            {specialties.map((specialty) => (
              <option key={specialty} value={specialty}>
                {specialty}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
        <label className="block">
          <span className="sr-only">City</span>
          <input value={filters.city} onChange={(event) => filters.setCity(event.target.value)} placeholder="City or area" className="form-field" />
        </label>
        <label className="block">
          <span className="sr-only">Consultation type</span>
          <select value={filters.mode} onChange={(event) => filters.setMode(event.target.value as ConsultationMode | "")} className="form-field">
            <option value="">Any type</option>
            <option value="in_clinic">In clinic</option>
            <option value="online">Online</option>
            <option value="home">Home visit</option>
          </select>
        </label>
        <label className="block">
          <span className="sr-only">Maximum fee in PKR</span>
          <input type="number" inputMode="numeric" min={0} value={filters.maxFee} onChange={(event) => filters.setMaxFee(event.target.value)} placeholder="Max fee (PKR)" className="form-field" />
        </label>
        <label className="block">
          <span className="sr-only">Minimum rating</span>
          <select value={filters.minRating} onChange={(event) => filters.setMinRating(event.target.value)} className="form-field">
            <option value="">Any rating</option>
            <option value="4.5">4.5 stars and up</option>
            <option value="4">4 stars and up</option>
            <option value="3">3 stars and up</option>
          </select>
        </label>
        <label className="block">
          <span className="sr-only">Sort by</span>
          <select value={filters.sort} onChange={(event) => filters.setSort(event.target.value as DoctorSort)} className="form-field">
            {SORTS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-700">
          <input
            type="checkbox"
            checked={filters.availableToday}
            onChange={(event) => filters.setAvailableToday(event.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-brand-blue focus:ring-brand-blue"
          />
          Available today
        </label>
        {directory.filtered ? (
          <Button variant="ghost" size="sm" onClick={directory.reset}>
            Clear filters
          </Button>
        ) : null}
      </div>
    </section>
  );
}

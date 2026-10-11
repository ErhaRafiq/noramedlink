import { Search } from "lucide-react";

import { ALL_SPECIALTIES } from "@/hooks/doctors/use-doctor-directory";

type Filters = {
  search: string;
  setSearch: (value: string) => void;
  specialty: string;
  setSpecialty: (value: string) => void;
  availableToday: boolean;
  setAvailableToday: (value: boolean) => void;
};

export function DoctorFilters({ filters, specialties }: { filters: Filters; specialties: string[] }) {
  return (
    <div className="grid gap-3 rounded-card border border-line bg-white p-4 shadow-card sm:grid-cols-[1fr_220px_auto] sm:items-center">
      <label className="relative block">
        <span className="sr-only">Search doctors</span>
        <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
        <input
          type="search"
          value={filters.search}
          onChange={(event) => filters.setSearch(event.target.value)}
          placeholder="Search by name, specialty or location"
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
      <label className="flex cursor-pointer items-center gap-2 whitespace-nowrap px-1 text-sm font-medium text-slate-700">
        <input
          type="checkbox"
          checked={filters.availableToday}
          onChange={(event) => filters.setAvailableToday(event.target.checked)}
          className="h-4 w-4 rounded border-slate-300 text-brand-blue focus:ring-brand-blue"
        />
        Available today
      </label>
    </div>
  );
}

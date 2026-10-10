/**
 * Report departments. Mirrors DEPARTMENTS in backend/services/ocr_space_service.py: the
 * backend files every report under one of these slugs, and the acceptance tests check
 * that /patient/reports/tiles returns exactly this set. Change both sides together.
 */
export const DEPARTMENTS = [
  { slug: "heart", label: "Heart" },
  { slug: "kidney", label: "Kidney" },
  { slug: "ortho", label: "Ortho" },
  { slug: "lab", label: "Lab" },
  { slug: "medicine", label: "Medicine" },
  { slug: "general", label: "General" },
] as const;

export type DepartmentSlug = (typeof DEPARTMENTS)[number]["slug"];

const SLUGS = new Set<string>(DEPARTMENTS.map((d) => d.slug));

export function isDepartmentSlug(value: string | null | undefined): value is DepartmentSlug {
  return SLUGS.has((value ?? "").toLowerCase());
}

/** A report's department slug, or "general" when it is missing or unknown. */
export function toDepartmentSlug(value: string | null | undefined): DepartmentSlug {
  const normalized = (value ?? "").toLowerCase().trim();
  return isDepartmentSlug(normalized) ? normalized : "general";
}

export function departmentLabel(slug: string | null | undefined) {
  const found = DEPARTMENTS.find((d) => d.slug === toDepartmentSlug(slug));
  return found?.label ?? "General";
}

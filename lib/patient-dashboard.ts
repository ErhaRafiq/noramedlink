import type { PatientReportCategorySummary } from "@/lib/types";

export const REPORT_CATEGORIES = [
  { id: "heart", label: "Heart", icon: "HeartPulse", keywords: ["ecg", "echo", "ldl", "hdl", "cholesterol", "troponin", "bp"] },
  { id: "liver", label: "Liver", icon: "FlaskConical", keywords: ["alt", "ast", "sgpt", "sgot", "bilirubin", "hepatitis"] },
  { id: "kidney", label: "Kidney", icon: "Droplets", keywords: ["creatinine", "urea", "egfr", "urine protein"] },
  { id: "blood", label: "Blood", icon: "Beaker", keywords: ["cbc", "hemoglobin", "wbc", "rbc", "platelets"] },
  { id: "diabetes", label: "Diabetes", icon: "Gauge", keywords: ["hba1c", "fasting glucose", "random sugar", "blood sugar"] },
  { id: "ortho", label: "Ortho", icon: "Bone", keywords: ["x-ray", "xray", "mri", "fracture", "bone", "joint", "spine"] },
  { id: "prescriptions", label: "Prescriptions", icon: "Pill", keywords: ["tablet", "capsule", "syrup", "dose", "mg", "daily", "twice daily"] },
  { id: "general", label: "General", icon: "FileText", keywords: [] },
] as const;

export type ReportCategoryId = (typeof REPORT_CATEGORIES)[number]["id"];

export const REPORT_CATEGORY_KEYWORDS: Record<ReportCategoryId, string[]> = {
  heart: ["ecg", "echo", "ldl", "hdl", "cholesterol", "troponin", "bp", "blood pressure"],
  liver: ["alt", "ast", "sgpt", "sgot", "bilirubin", "hepatitis", "lft"],
  kidney: ["creatinine", "urea", "egfr", "urine protein", "renal"],
  blood: ["cbc", "hemoglobin", "haemoglobin", "wbc", "rbc", "platelets", "blood count"],
  diabetes: ["hba1c", "fasting glucose", "random sugar", "blood sugar", "glucose", "a1c"],
  ortho: ["x-ray", "xray", "mri", "fracture", "bone", "joint", "spine", "orthopedic"],
  prescriptions: ["tablet", "capsule", "syrup", "dose", "mg", "daily", "twice daily", "prescription"],
  general: [],
};

const SPECIALIST_BY_CATEGORY: Record<ReportCategoryId, string> = {
  heart: "Cardiologist",
  liver: "Hepatologist",
  kidney: "Nephrologist",
  blood: "Hematologist",
  diabetes: "Endocrinologist",
  ortho: "Orthopedic Specialist",
  prescriptions: "Primary Care Doctor",
  general: "General Physician",
};

const REPORT_TYPE_BY_CATEGORY: Record<ReportCategoryId, string> = {
  heart: "Cardiac report",
  liver: "Liver panel",
  kidney: "Renal function report",
  blood: "Blood work",
  diabetes: "Diabetes report",
  ortho: "Orthopedic imaging",
  prescriptions: "Prescription",
  general: "General medical report",
};

export function normalizeReportCategory(value: string | null | undefined): ReportCategoryId {
  const normalized = (value ?? "").toLowerCase().trim();
  const found = REPORT_CATEGORIES.find((category) => category.id === normalized);
  return (found?.id ?? "general") as ReportCategoryId;
}

export function classifyReportCategory(text: string, fileName?: string | null): ReportCategoryId {
  const haystack = `${fileName ?? ""} ${text}`.toLowerCase();
  for (const [category, keywords] of Object.entries(REPORT_CATEGORY_KEYWORDS) as Array<[ReportCategoryId, string[]]>) {
    if (category === "general") {
      continue;
    }
    if (keywords.some((keyword) => haystack.includes(keyword))) {
      return category;
    }
  }
  return "general";
}

export function reportTypeForCategory(category: ReportCategoryId) {
  return REPORT_TYPE_BY_CATEGORY[category] ?? REPORT_TYPE_BY_CATEGORY.general;
}

export function specialistForCategory(category: ReportCategoryId) {
  return SPECIALIST_BY_CATEGORY[category] ?? SPECIALIST_BY_CATEGORY.general;
}

export function categoryStatusForCount(count: number, latestStatus?: string | null) {
  if (count === 0) {
    return "No documents";
  }
  if ((latestStatus ?? "").toLowerCase().includes("high")) {
    return "Review";
  }
  if ((latestStatus ?? "").toLowerCase().includes("caution")) {
    return "Monitor";
  }
  return "Stable";
}

export function buildCategorySummaries(reports: Array<{ category: string; ocr_status?: string | null; uploadDate?: string | Date | null }>): PatientReportCategorySummary[] {
  return REPORT_CATEGORIES.map((category) => {
    const matching = reports.filter((report) => normalizeReportCategory(report.category) === category.id);
    const latest = matching.sort((first, second) => new Date(String(second.uploadDate ?? 0)).getTime() - new Date(String(first.uploadDate ?? 0)).getTime())[0];

    return {
      category: category.id,
      document_count: matching.length,
      latest_status: categoryStatusForCount(matching.length, latest?.ocr_status ?? null),
      latest_upload_date: latest?.uploadDate ? new Date(String(latest.uploadDate)).toISOString() : null,
      icon: category.icon,
    };
  });
}

export function classifyRiskFlags(text: string) {
  const lower = text.toLowerCase();
  const flags: string[] = [];

  if (/(chest pain|shortness of breath|palpitations|troponin|ecg|echo)/.test(lower)) {
    flags.push("Possible heart-related risk");
  }
  if (/(alt|ast|sgpt|sgot|bilirubin|hepatitis|jaundice)/.test(lower)) {
    flags.push("Possible liver enzyme elevation");
  }
  if (/(hba1c|glucose|blood sugar|diabetes|sugar)/.test(lower)) {
    flags.push("Blood sugar variation detected");
  }
  if (/(creatinine|urea|egfr|urine protein)/.test(lower)) {
    flags.push("Possible kidney function variation");
  }

  if (flags.length === 0 && lower.trim().length > 0) {
    flags.push("Please consult your doctor");
  }

  return flags.slice(0, 4);
}

export function buildShortSummary(text: string) {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length <= 220) {
    return cleaned;
  }
  return `${cleaned.slice(0, 217).trim()}...`;
}

export function buildMedicalDisclaimer() {
  return "These insights are not a diagnosis. Please consult your doctor.";
}

export function buildPatientFriendlySummary(category: ReportCategoryId, text: string) {
  const specialist = specialistForCategory(category);
  const summary = buildShortSummary(text);
  return summary.length > 0
    ? `This ${reportTypeForCategory(category).toLowerCase()} suggests a discussion with a ${specialist}. ${summary}`
    : `Please discuss this ${reportTypeForCategory(category).toLowerCase()} with a ${specialist}.`;
}


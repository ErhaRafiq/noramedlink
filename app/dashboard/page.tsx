"use client";

import Link from "next/link";
import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type Vitals = {
  id: number;
  bloodPressure: string;
  sugarLevel: string;
  createdAt: string;
};

type Appointment = {
  id: number;
  doctorName: string;
  date: string;
};

type Medication = {
  id: number;
  name: string;
  dosage: string;
  status: string;
};

type Reminder = {
  id: number;
  title: string;
  dueAt: string;
  status: string;
};

type MedicalRecord = {
  id: number;
  title: string;
  fileName: string;
  imageUrl?: string;
  extractedText?: string | null;
  scanStatus?: string;
  createdAt: string;
};

type DashboardData = {
  latestVitals: Vitals | null;
  vitalsHistory: Vitals[];
  upcomingAppointment: Appointment | null;
  medications: Medication[];
  reminders: Reminder[];
  medicalRecords: MedicalRecord[];
};

type MedicalHistoryCategory = {
  id: string;
  title: string;
  description: string;
  accentClass: string;
  iconClass: string;
  keywords: string[];
};

type PatientRisk = {
  id: string;
  title: string;
  level: "High" | "Moderate" | "Watch";
  summary: string;
  evidence: string[];
  action: string;
};

const emptyDashboard: DashboardData = {
  latestVitals: null,
  vitalsHistory: [],
  upcomingAppointment: null,
  medications: [],
  reminders: [],
  medicalRecords: [],
};

const medicalHistoryCategories: MedicalHistoryCategory[] = [
  {
    id: "heart",
    title: "Heart",
    description: "Blood pressure, cardiac reports, chest pain, ECG, and cholesterol.",
    accentClass: "border-rose-100 bg-rose-50 text-rose-700",
    iconClass: "bg-rose-100 text-rose-600",
    keywords: [
      "heart",
      "cardiac",
      "cardio",
      "ecg",
      "ekg",
      "cholesterol",
      "lipid",
      "ldl",
      "hdl",
      "triglyceride",
      "hypertension",
      "blood pressure",
      "bp",
      "angina",
      "chest pain",
    ],
  },
  {
    id: "kidney",
    title: "Kidney",
    description: "Creatinine, urea, urine reports, dialysis, and renal conditions.",
    accentClass: "border-cyan-100 bg-cyan-50 text-cyan-700",
    iconClass: "bg-cyan-100 text-cyan-700",
    keywords: [
      "kidney",
      "renal",
      "creatinine",
      "urea",
      "urine",
      "kft",
      "rft",
      "egfr",
      "uric acid",
      "dialysis",
      "nephro",
      "proteinuria",
    ],
  },
  {
    id: "diabetes",
    title: "Diabetes",
    description: "Sugar readings, HbA1c, insulin, glucose, and diabetic care.",
    accentClass: "border-emerald-100 bg-emerald-50 text-emerald-700",
    iconClass: "bg-emerald-100 text-emerald-700",
    keywords: [
      "diabetes",
      "diabetic",
      "sugar",
      "glucose",
      "hba1c",
      "insulin",
      "metformin",
    ],
  },
  {
    id: "liver",
    title: "Liver",
    description: "LFT, bilirubin, hepatitis, jaundice, SGPT, and SGOT.",
    accentClass: "border-amber-100 bg-amber-50 text-amber-700",
    iconClass: "bg-amber-100 text-amber-700",
    keywords: [
      "liver",
      "hepatic",
      "hepatitis",
      "bilirubin",
      "jaundice",
      "sgpt",
      "sgot",
      "alt",
      "ast",
      "alkaline phosphatase",
      "albumin",
      "lft",
    ],
  },
  {
    id: "lungs",
    title: "Lungs",
    description: "Asthma, cough, breathing, oxygen, pneumonia, and chest X-ray.",
    accentClass: "border-blue-100 bg-blue-50 text-blue-700",
    iconClass: "bg-blue-100 text-blue-700",
    keywords: [
      "lung",
      "lungs",
      "asthma",
      "cough",
      "breathing",
      "oxygen",
      "pneumonia",
      "chest xray",
      "chest x-ray",
      "spo2",
    ],
  },
  {
    id: "brain",
    title: "Brain",
    description: "Neurology, headache, stroke, seizure, migraine, and nerve reports.",
    accentClass: "border-violet-100 bg-violet-50 text-violet-700",
    iconClass: "bg-violet-100 text-violet-700",
    keywords: [
      "brain",
      "neuro",
      "neurology",
      "stroke",
      "seizure",
      "migraine",
      "headache",
      "nerve",
    ],
  },
  {
    id: "stomach",
    title: "Stomach",
    description: "Digestive, gastric, abdomen, acidity, ulcer, and bowel concerns.",
    accentClass: "border-orange-100 bg-orange-50 text-orange-700",
    iconClass: "bg-orange-100 text-orange-700",
    keywords: [
      "stomach",
      "gastric",
      "abdomen",
      "abdominal",
      "digestive",
      "ulcer",
      "acidity",
      "bowel",
      "gastro",
    ],
  },
  {
    id: "bone",
    title: "Bones",
    description: "Fractures, joints, arthritis, back pain, calcium, and orthopedic care.",
    accentClass: "border-slate-200 bg-slate-50 text-slate-700",
    iconClass: "bg-slate-200 text-slate-700",
    keywords: [
      "bone",
      "joint",
      "fracture",
      "arthritis",
      "orthopedic",
      "ortho",
      "calcium",
      "spine",
      "back pain",
    ],
  },
  {
    id: "blood",
    title: "Blood",
    description: "CBC, hemoglobin, platelets, anemia, and blood test reports.",
    accentClass: "border-red-100 bg-red-50 text-red-700",
    iconClass: "bg-red-100 text-red-700",
    keywords: [
      "blood",
      "cbc",
      "hemoglobin",
      "haemoglobin",
      "platelet",
      "anemia",
      "wbc",
      "rbc",
      "mch",
      "mcv",
      "pcv",
    ],
  },
  {
    id: "general",
    title: "General",
    description: "Records that do not clearly match one body-system tile yet.",
    accentClass: "border-slate-200 bg-white text-slate-700",
    iconClass: "bg-slate-100 text-slate-700",
    keywords: [],
  },
];

const medicalProblemKeywords = [
  "abnormal",
  "acute",
  "anemia",
  "angina",
  "asthma",
  "blockage",
  "chronic",
  "critical",
  "diabetes",
  "disease",
  "failure",
  "fracture",
  "hepatitis",
  "high",
  "hypertension",
  "infection",
  "inflammation",
  "low",
  "migraine",
  "pneumonia",
  "positive",
  "problem",
  "renal",
  "severe",
  "stroke",
  "ulcer",
];

const seriousThreatKeywords = [
  "acute",
  "blockage",
  "critical",
  "emergency",
  "failure",
  "heart attack",
  "high bilirubin",
  "high blood sugar",
  "high creatinine",
  "high troponin",
  "low hemoglobin",
  "low platelets",
  "malignant",
  "panic",
  "positive",
  "sepsis",
  "severe",
  "stroke",
  "very high",
  "very low",
];

function getStoredValue(key: string) {
  if (typeof window === "undefined") {
    return "";
  }

  return localStorage.getItem(key) ?? "";
}

function parseBloodPressure(value?: string) {
  const match = value?.match(/(\d+)\s*\/\s*(\d+)/);

  if (!match) {
    return null;
  }

  return {
    systolic: Number(match[1]),
    diastolic: Number(match[2]),
  };
}

function parseSugarLevel(value?: string) {
  const match = value?.match(/\d+/);

  return match ? Number(match[0]) : null;
}

function getVitalsProblemCategoryIds(vitals: Vitals | null) {
  const problemCategoryIds: string[] = [];
  const bloodPressureReading = parseBloodPressure(vitals?.bloodPressure);
  const sugarReading = parseSugarLevel(vitals?.sugarLevel);

  if (
    bloodPressureReading &&
    (bloodPressureReading.systolic >= 140 || bloodPressureReading.diastolic >= 90)
  ) {
    problemCategoryIds.push("heart");
  }

  if (sugarReading !== null && sugarReading >= 180) {
    problemCategoryIds.push("diabetes");
  }

  return problemCategoryIds;
}

function getPatientRiskAnalysis(dashboard: DashboardData): PatientRisk[] {
  const risks: PatientRisk[] = [];
  const latestBloodPressure = parseBloodPressure(dashboard.latestVitals?.bloodPressure);
  const latestSugar = parseSugarLevel(dashboard.latestVitals?.sugarLevel);
  const highBloodPressureReadings = dashboard.vitalsHistory.filter((vital) => {
    const reading = parseBloodPressure(vital.bloodPressure);

    return Boolean(
      reading && (reading.systolic >= 130 || reading.diastolic >= 80),
    );
  });
  const veryHighBloodPressureReadings = dashboard.vitalsHistory.filter((vital) => {
    const reading = parseBloodPressure(vital.bloodPressure);

    return Boolean(
      reading && (reading.systolic >= 140 || reading.diastolic >= 90),
    );
  });
  const highSugarReadings = dashboard.vitalsHistory.filter((vital) => {
    const sugar = parseSugarLevel(vital.sugarLevel);

    return sugar !== null && sugar >= 180;
  });
  const recordText = dashboard.medicalRecords.map(getRecordSearchText).join(" ");
  const hasRecordKeyword = (keywords: string[]) =>
    keywords.some((keyword) => recordText.includes(keyword));

  if (
    latestBloodPressure &&
    (latestBloodPressure.systolic >= 140 || latestBloodPressure.diastolic >= 90)
  ) {
    risks.push({
      id: "heart",
      title: "Heart and blood pressure risk",
      level: "High",
      summary: "Latest blood pressure is in a high range and may increase future heart or stroke risk.",
      evidence: [
        `Latest BP: ${dashboard.latestVitals?.bloodPressure}`,
        `${veryHighBloodPressureReadings.length} recent high BP reading(s) found`,
      ],
      action: "Book a doctor review and keep monitoring blood pressure regularly.",
    });
  } else if (highBloodPressureReadings.length >= 2) {
    risks.push({
      id: "heart",
      title: "Blood pressure trend to watch",
      level: "Moderate",
      summary: "Recent readings show repeated elevated blood pressure patterns.",
      evidence: [`${highBloodPressureReadings.length} elevated BP reading(s) in recent history`],
      action: "Review lifestyle and medication plan with a clinician if readings stay elevated.",
    });
  }

  if (latestSugar !== null && latestSugar >= 180) {
    risks.push({
      id: "diabetes",
      title: "Diabetes or glucose control risk",
      level: "High",
      summary: "Latest sugar reading is high and may indicate poor glucose control.",
      evidence: [
        `Latest sugar: ${dashboard.latestVitals?.sugarLevel}`,
        `${highSugarReadings.length} recent high sugar reading(s) found`,
      ],
      action: "Discuss sugar control, diet, and medicines with a doctor.",
    });
  } else if (highSugarReadings.length >= 2 || hasRecordKeyword(["hba1c", "diabetes", "diabetic"])) {
    risks.push({
      id: "diabetes",
      title: "Glucose trend to watch",
      level: "Moderate",
      summary: "Reports or recent readings suggest glucose-related follow-up may be needed.",
      evidence: [
        highSugarReadings.length > 0
          ? `${highSugarReadings.length} high sugar reading(s)`
          : "Diabetes-related terms found in uploaded records",
      ],
      action: "Keep a sugar log and review HbA1c or glucose reports with a clinician.",
    });
  }

  if (hasRecordKeyword(["kidney", "renal", "creatinine", "urea", "proteinuria", "dialysis"])) {
    risks.push({
      id: "kidney",
      title: "Kidney follow-up risk",
      level: latestBloodPressure && latestBloodPressure.systolic >= 140 ? "High" : "Moderate",
      summary: "Uploaded records mention kidney-related findings, which can be affected by blood pressure and diabetes.",
      evidence: ["Kidney-related terms found in scanned records"],
      action: "Ask a doctor about kidney function tests such as creatinine, urea, and urine protein.",
    });
  }

  if (hasRecordKeyword(["asthma", "pneumonia", "oxygen", "spo2", "shortness of breath", "breathing"])) {
    risks.push({
      id: "lungs",
      title: "Respiratory risk",
      level: "Moderate",
      summary: "Uploaded records mention breathing or lung-related concerns.",
      evidence: ["Lung or oxygen-related terms found in scanned records"],
      action: "Track symptoms and seek care quickly for shortness of breath or low oxygen.",
    });
  }

  if (hasRecordKeyword(["stroke", "seizure", "migraine", "neurology", "headache"])) {
    risks.push({
      id: "brain",
      title: "Neurology follow-up risk",
      level: "Moderate",
      summary: "Uploaded records mention brain, nerve, or headache-related concerns.",
      evidence: ["Neurology-related terms found in scanned records"],
      action: "Review symptoms and reports with a neurologist or primary doctor.",
    });
  }

  if (hasRecordKeyword(["hepatitis", "bilirubin", "jaundice", "sgpt", "sgot", "lft"])) {
    risks.push({
      id: "liver",
      title: "Liver follow-up risk",
      level: "Moderate",
      summary: "Uploaded records mention liver-related findings.",
      evidence: ["Liver-related terms found in scanned records"],
      action: "Discuss liver function tests and symptoms with a clinician.",
    });
  }

  if (risks.length === 0) {
    risks.push({
      id: "general",
      title: "No major risk pattern detected",
      level: "Watch",
      summary: "Current dashboard data does not show a strong future-risk signal.",
      evidence: ["Analysis used latest vitals, recent vitals, and uploaded report text"],
      action: "Keep uploading reports and recording vitals so predictions improve over time.",
    });
  }

  return risks.slice(0, 4);
}

function formatDate(value?: string) {
  if (!value) {
    return "Not scheduled";
  }

  return new Date(value).toLocaleString();
}

function isLegacyScannerSetupText(value?: string | null) {
  return Boolean(
    value?.includes(
      "AI scanning is not configured yet. Add a backend OCR provider to enable automatic text extraction.",
    ),
  );
}

function getRecordSearchText(record: MedicalRecord) {
  return `${record.title} ${record.fileName} ${record.extractedText ?? ""}`.toLowerCase();
}

function recordHasProblem(record: MedicalRecord) {
  const searchText = getRecordSearchText(record);

  return medicalProblemKeywords.some((keyword) => searchText.includes(keyword));
}

function getSeriousThreatAlert(record: MedicalRecord) {
  const searchText = getRecordSearchText(record);

  if (!seriousThreatKeywords.some((keyword) => searchText.includes(keyword))) {
    return "";
  }

  if (searchText.includes("high blood sugar") || searchText.includes("very high")) {
    return "Serious alert: this report may show a very high reading. Please contact a doctor soon.";
  }

  if (searchText.includes("low hemoglobin") || searchText.includes("low platelets")) {
    return "Serious alert: this report may show a risky blood-count problem that needs medical review.";
  }

  if (searchText.includes("high creatinine") || searchText.includes("failure")) {
    return "Serious alert: this report may show kidney or organ stress that needs prompt medical review.";
  }

  if (searchText.includes("positive")) {
    return "Serious alert: this report includes a positive result. A doctor should confirm what it means.";
  }

  return "Serious alert: this report contains urgent warning words. Please review it with a doctor.";
}

function recordHasSeriousThreat(record: MedicalRecord) {
  return getSeriousThreatAlert(record).length > 0;
}

function getMedicalHistoryCategories(record: MedicalRecord) {
  const searchText = getRecordSearchText(record);
  const matchedCategories = medicalHistoryCategories.filter(
    (category) =>
      category.keywords.length > 0 &&
      category.keywords.some((keyword) => searchText.includes(keyword)),
  );

  return matchedCategories.length > 0
    ? matchedCategories
    : [medicalHistoryCategories[medicalHistoryCategories.length - 1]];
}

function getRecordSummary(record: MedicalRecord) {
  const extractedText = isLegacyScannerSetupText(record.extractedText)
    ? ""
    : record.extractedText?.trim();

  if (!extractedText) {
    return "Uploaded record waiting for readable medical details.";
  }

  return extractedText.length > 140
    ? `${extractedText.slice(0, 140).trim()}...`
    : extractedText;
}

function getRecordImageStyle(record: MedicalRecord) {
  if (!record.imageUrl) {
    return undefined;
  }

  return {
    backgroundImage: `url("${record.imageUrl}")`,
  };
}

function OrganLogo({ id }: { id: string }) {
  const commonProps = {
    className: "h-11 w-11",
    fill: "none",
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    viewBox: "0 0 48 48",
  };

  if (id === "heart") {
    return (
      <svg aria-hidden="true" {...commonProps}>
        <path d="M24 40s-13.6-8.6-17.6-17C2.7 15.1 7.5 7.8 15 7.8c4.2 0 6.9 2.2 9 5 2.1-2.8 4.8-5 9-5 7.5 0 12.3 7.3 8.6 15.2C37.6 31.4 24 40 24 40Z" fill="#ff4d6d" stroke="#9f1239" strokeWidth="2.4" />
        <path d="M12 24h7l2.4-5.2L26 31l2.5-7H36" stroke="#fff" strokeWidth="2.8" />
      </svg>
    );
  }

  if (id === "kidney") {
    return (
      <svg aria-hidden="true" {...commonProps}>
        <path d="M18.5 9c-6 0-10.5 6.3-10.5 14.1C8 31.5 12.6 36 17.3 36c3.9 0 5.7-3 5.7-6.6V14.8C23 11.3 21.5 9 18.5 9Z" fill="#22d3ee" stroke="#0e7490" strokeWidth="2.2" />
        <path d="M29.5 9C35.5 9 40 15.3 40 23.1 40 31.5 35.4 36 30.7 36c-3.9 0-5.7-3-5.7-6.6V14.8C25 11.3 26.5 9 29.5 9Z" fill="#67e8f9" stroke="#0e7490" strokeWidth="2.2" />
        <path d="M24 18h-5M24 18h5" stroke="#fff" strokeWidth="2.6" />
      </svg>
    );
  }

  if (id === "diabetes" || id === "blood") {
    return (
      <svg aria-hidden="true" {...commonProps}>
        <path d="M24 6s12 13.5 12 22.5a12 12 0 0 1-24 0C12 19.5 24 6 24 6Z" fill={id === "blood" ? "#ef4444" : "#10b981"} stroke={id === "blood" ? "#991b1b" : "#047857"} strokeWidth="2.4" />
        <path d="M18.5 29c2.1 3.4 7.3 4.5 11 1.5" stroke="#fff" strokeWidth="2.8" />
        {id === "diabetes" ? <path d="M20 22h8M24 18v8" stroke="#fff" strokeWidth="2.6" /> : null}
      </svg>
    );
  }

  if (id === "liver") {
    return (
      <svg aria-hidden="true" {...commonProps}>
        <path d="M6 24c0-9 7.5-13.5 18.8-13.5h15.7c1.8 0 3 1.5 2.6 3.3-2.4 9.8-9.2 18.3-18.9 21.9C14.3 39.3 6 34.1 6 24Z" fill="#f59e0b" stroke="#b45309" strokeWidth="2.4" />
        <path d="M24 10.5c1.8 7.2 1.2 14-1.8 20.2" stroke="#fff7ed" strokeWidth="2.8" />
      </svg>
    );
  }

  if (id === "lungs") {
    return (
      <svg aria-hidden="true" {...commonProps}>
        <path d="M24 7v15" stroke="#1d4ed8" strokeWidth="3" />
        <path d="M23.8 22.5c-7-8.1-12-9.3-15-5.4-3.3 4.2-3.5 15.6 2 19.5 4.8 3.4 10.8-1.4 13-14.1Z" fill="#60a5fa" stroke="#1d4ed8" strokeWidth="2.4" />
        <path d="M24.2 22.5c7-8.1 12-9.3 15-5.4 3.3 4.2 3.5 15.6-2 19.5-4.8 3.4-10.8-1.4-13-14.1Z" fill="#93c5fd" stroke="#1d4ed8" strokeWidth="2.4" />
        <path d="M16 25c1.9 2.1 3.4 5.1 4 9M32 25c-1.9 2.1-3.4 5.1-4 9" stroke="#eff6ff" strokeWidth="2" />
      </svg>
    );
  }

  if (id === "brain") {
    return (
      <svg aria-hidden="true" {...commonProps}>
        <path d="M16.5 36c-5.1-1-9-5.6-9-11.1 0-3.9 2-7.3 5-9.3.5-4.7 4.4-8.1 9.2-8.1 2.7 0 5.1 1.2 6.8 3.1 6.6-.9 12.1 4.2 12.1 11 0 7.2-5.5 13.2-12.6 14.2Z" fill="#a855f7" stroke="#6d28d9" strokeWidth="2.4" />
        <path d="M18 18c3-1.5 5.5-.6 7.5 2.6M30 16.5c2.7 1.1 4.2 3.2 4.5 6.3M18 27c2.1 2.4 4.8 3.3 7.8 2.7" stroke="#faf5ff" strokeWidth="2.4" />
      </svg>
    );
  }

  if (id === "stomach") {
    return (
      <svg aria-hidden="true" {...commonProps}>
        <path d="M27 7.5c-3.6 4.5-3 8.4 1.7 11.6 4.8 3.3 8.1 6.9 6.9 12.3-1 5.4-6 9.1-12.1 9.1-7.4 0-12.9-5.2-12.9-12.1 0-7.4 6.4-9.9 12.3-10.4" fill="#fb923c" stroke="#c2410c" strokeWidth="2.4" />
        <path d="M27 7.5h7.5M19 27c3.5 2.4 7 2.4 10.5 0" stroke="#fff7ed" strokeWidth="2.6" />
      </svg>
    );
  }

  if (id === "bone") {
    return (
      <svg aria-hidden="true" {...commonProps}>
        <path d="M15.5 15.5 32.5 32.5" stroke="#475569" strokeWidth="5" />
        <path d="M11.7 19.2A6 6 0 1 1 19.2 11.7" fill="#e2e8f0" stroke="#475569" strokeWidth="2.4" />
        <path d="M28.8 36.3a6 6 0 1 0 7.5-7.5" fill="#e2e8f0" stroke="#475569" strokeWidth="2.4" />
      </svg>
    );
  }

  return (
    <svg aria-hidden="true" {...commonProps}>
      <path d="M12 8h18l6 6v26H12z" fill="#60a5fa" stroke="#1d4ed8" strokeWidth="2.4" />
      <path d="M30 8v7h7" stroke="#eff6ff" strokeWidth="2.4" />
      <path d="M18 22h12M18 28h12M18 34h8" stroke="#eff6ff" strokeWidth="2.4" />
    </svg>
  );
}

function getBodyFocusLabel(id: string) {
  const labels: Record<string, string> = {
    blood: "Blood",
    bone: "Bones",
    brain: "Brain",
    diabetes: "Diabetes",
    general: "General record",
    heart: "Heart",
    kidney: "Kidneys",
    liver: "Liver",
    lungs: "Lungs",
    stomach: "Stomach",
  };

  return labels[id] ?? "Organ";
}

function CuteLogo({
  type,
  size = "md",
}: {
  type: string;
  size?: "sm" | "md" | "lg";
}) {
  const sizeClass =
    size === "lg" ? "cute-logo-lg" : size === "sm" ? "cute-logo-sm" : "";
  const iconClass = size === "sm" ? "h-6 w-6" : size === "lg" ? "h-10 w-10" : "h-8 w-8";

  if (
    [
      "heart",
      "kidney",
      "diabetes",
      "liver",
      "lungs",
      "brain",
      "stomach",
      "bone",
      "blood",
      "general",
    ].includes(type)
  ) {
    return (
      <span className={`cute-logo ${sizeClass} logo-${type}`}>
        <span className="cute-sparkle">*</span>
        <OrganLogo id={type} />
      </span>
    );
  }

  const logoClass = `cute-logo ${sizeClass} logo-${type}`;

  return (
    <span className={logoClass}>
      <span className="cute-sparkle">*</span>
      {type === "appointment" ? (
        <svg aria-hidden="true" className={iconClass} fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" viewBox="0 0 24 24">
          <path d="M8 2v4" />
          <path d="M16 2v4" />
          <path d="M3 10h18" />
          <path d="M5 4h14v17H5z" />
          <path d="m9 15 2 2 4-5" />
        </svg>
      ) : type === "reminder" ? (
        <svg aria-hidden="true" className={iconClass} fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" viewBox="0 0 24 24">
          <path d="M12 6v6l4 2" />
          <path d="M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
          <path d="M8 2 5 5" />
          <path d="m16 2 3 3" />
        </svg>
      ) : type === "medicine" ? (
        <svg aria-hidden="true" className={iconClass} fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" viewBox="0 0 24 24">
          <path d="m10.5 20.5 10-10a4 4 0 0 0-5.7-5.7l-10 10a4 4 0 0 0 5.7 5.7Z" />
          <path d="m8.5 10.5 5 5" />
        </svg>
      ) : type === "scanner" || type === "records" ? (
        <svg aria-hidden="true" className={iconClass} fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" viewBox="0 0 24 24">
          <path d="M7 3h7l5 5v13H7z" />
          <path d="M14 3v6h6" />
          <path d="M9 14h6" />
          <path d="M9 18h4" />
        </svg>
      ) : (
        <span className={iconClass}>
          <OrganLogo id="heart" />
        </span>
      )}
    </span>
  );
}

function compressImageFile(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = () => {
      if (typeof reader.result !== "string") {
        reject(new Error("Unable to read image."));
        return;
      }

      const image = new Image();
      image.onload = () => {
        const maxSize = 1600;
        const scale = Math.min(1, maxSize / Math.max(image.width, image.height));
        const width = Math.max(1, Math.round(image.width * scale));
        const height = Math.max(1, Math.round(image.height * scale));
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");

        if (!context) {
          resolve(reader.result as string);
          return;
        }

        canvas.width = width;
        canvas.height = height;
        context.fillStyle = "#ffffff";
        context.fillRect(0, 0, width, height);
        context.drawImage(image, 0, 0, width, height);
        resolve(canvas.toDataURL("image/jpeg", 0.88));
      };
      image.onerror = () => resolve(reader.result as string);
      image.src = reader.result;
    };
    reader.onerror = () => reject(new Error("Unable to read image."));
    reader.readAsDataURL(file);
  });
}

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState<DashboardData>(emptyDashboard);
  const [bloodPressure, setBloodPressure] = useState("");
  const [sugarLevel, setSugarLevel] = useState("");
  const [medicineReminderName, setMedicineReminderName] = useState("");
  const [medicineReminderAt, setMedicineReminderAt] = useState("");
  const [recordFileName, setRecordFileName] = useState("");
  const [recordImageData, setRecordImageData] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSavingVitals, setIsSavingVitals] = useState(false);
  const [isSavingMedicineReminder, setIsSavingMedicineReminder] = useState(false);
  const [isUploadingRecord, setIsUploadingRecord] = useState(false);
  const [deletingRecordId, setDeletingRecordId] = useState<number | null>(null);
  const [activeMedicalTileId, setActiveMedicalTileId] = useState("heart");
  const [isMedicalTileOpen, setIsMedicalTileOpen] = useState(false);
  const [activeRiskId, setActiveRiskId] = useState("");
  const [isRiskOpen, setIsRiskOpen] = useState(false);
  const [activeUploadRecordId, setActiveUploadRecordId] = useState<number | null>(null);
  const [isUploadDetailsOpen, setIsUploadDetailsOpen] = useState(false);
  const [dashboardOtp, setDashboardOtp] = useState<{ code: string; expiresAt: string } | null>(null);
  const [isGeneratingOtp, setIsGeneratingOtp] = useState(false);

  const latestVitals = dashboard.latestVitals;

  const medicalHistoryTiles = useMemo(() => {
    const vitalProblemCategoryIds = getVitalsProblemCategoryIds(latestVitals);

    return medicalHistoryCategories.map((category) => {
      const records = dashboard.medicalRecords.filter(
        (record) =>
          getMedicalHistoryCategories(record).some(
            (recordCategory) => recordCategory.id === category.id,
          ),
      );
      const problemRecord = records.find(recordHasProblem);
      const seriousThreatRecord = records.find(recordHasSeriousThreat);
      const hasVitalsProblem = vitalProblemCategoryIds.includes(category.id);
      const latestRecord = records[0];

      return {
        ...category,
        records,
        latestSummary: latestRecord ? getRecordSummary(latestRecord) : "",
        hasProblem: hasVitalsProblem || Boolean(problemRecord) || Boolean(seriousThreatRecord),
        hasSeriousThreat: Boolean(seriousThreatRecord),
        problemLabel: hasVitalsProblem
          ? "Latest vitals need attention"
          : seriousThreatRecord
            ? "Report may show a serious threat"
          : problemRecord
            ? "Report text mentions a concern"
            : "",
      };
    });
  }, [dashboard.medicalRecords, latestVitals]);

  const activeMedicalTile =
    medicalHistoryTiles.find((tile) => tile.id === activeMedicalTileId) ?? medicalHistoryTiles[0];
  const activeProblemRecords = activeMedicalTile.records.filter(recordHasProblem);

  const openMedicalTile = (tileId: string) => {
    setActiveMedicalTileId(tileId);
    setIsMedicalTileOpen(true);
  };

  const alerts = useMemo(() => {
    const nextAlerts: string[] = [];
    const bloodPressureReading = parseBloodPressure(latestVitals?.bloodPressure);
    const sugarReading = parseSugarLevel(latestVitals?.sugarLevel);

    if (
      bloodPressureReading &&
      (bloodPressureReading.systolic >= 140 || bloodPressureReading.diastolic >= 90)
    ) {
      nextAlerts.push("Blood pressure is high. Consider contacting your doctor.");
    }

    if (sugarReading !== null && sugarReading >= 180) {
      nextAlerts.push("Sugar level is high. Monitor closely and follow your care plan.");
    }

    return nextAlerts;
  }, [latestVitals]);

  const problemTiles = medicalHistoryTiles.filter((tile) => tile.hasProblem);
  const healthStatus = alerts.length > 0 || problemTiles.length > 0 ? "Needs attention" : "Stable";
  const primaryAlert =
    alerts[0] ??
    problemTiles[0]?.problemLabel ??
    "No urgent health alerts detected from your latest dashboard data.";
  const patientRisks = useMemo(() => getPatientRiskAnalysis(dashboard), [dashboard]);
  const activeRisk = patientRisks.find((risk) => risk.id === activeRiskId) ?? patientRisks[0];
  const activeUploadRecord =
    dashboard.medicalRecords.find((record) => record.id === activeUploadRecordId) ??
    dashboard.medicalRecords[0];

  const openRisk = (riskId: string) => {
    setActiveRiskId(riskId);
    setIsRiskOpen(true);
  };

  const openUploadDetails = (recordId?: number) => {
    setActiveUploadRecordId(recordId ?? dashboard.medicalRecords[0]?.id ?? null);
    setIsUploadDetailsOpen(true);
  };

  const deleteMedicalRecord = async (recordId: number) => {
    const userId = getStoredValue("userId");

    if (!userId) {
      setStatusMessage("Please login before removing reports.");
      return;
    }

    const shouldDelete = window.confirm(
      "Remove this report from all medical tiles? This cannot be undone.",
    );

    if (!shouldDelete) {
      return;
    }

    setDeletingRecordId(recordId);
    setStatusMessage("");

    try {
      const response = await fetch("/api/medical-records/delete", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ userId, recordId }),
      });
      const data = (await response.json()) as { message?: string };

      if (!response.ok) {
        setStatusMessage(data.message ?? "Unable to remove this report.");
        return;
      }

      setDashboard((currentDashboard) => ({
        ...currentDashboard,
        medicalRecords: currentDashboard.medicalRecords.filter(
          (record) => record.id !== recordId,
        ),
      }));
      setActiveUploadRecordId((currentRecordId) =>
        currentRecordId === recordId ? null : currentRecordId,
      );
      setStatusMessage(data.message ?? "Report removed from medical tiles.");
      await loadDashboard();
    } catch {
      setStatusMessage("Unable to remove this report. Please try again.");
    } finally {
      setDeletingRecordId(null);
    }
  };

  const generateDashboardOtp = async () => {
    const userId = getStoredValue("userId");

    if (!userId) {
      setStatusMessage("Please login before generating a doctor OTP.");
      return;
    }

    setIsGeneratingOtp(true);
    setStatusMessage("");

    try {
      const response = await fetch("/api/dashboard/access-otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId }),
      });
      const data = (await response.json()) as {
        message?: string;
        otp?: { code: string; expiresAt: string };
      };

      if (!response.ok || !data.otp) {
        setStatusMessage(data.message ?? "Unable to generate OTP.");
        return;
      }

      setDashboardOtp(data.otp);
      setStatusMessage("One-time doctor OTP generated. Share it only with your doctor.");
    } catch {
      setStatusMessage("Unable to generate OTP.");
    } finally {
      setIsGeneratingOtp(false);
    }
  };

  const copyDashboardOtp = async () => {
    if (!dashboardOtp) {
      return;
    }

    try {
      await navigator.clipboard.writeText(dashboardOtp.code);
      setStatusMessage("OTP copied. It can be used once and expires soon.");
    } catch {
      setStatusMessage(`Your one-time OTP is ${dashboardOtp.code}`);
    }
  };

  const loadDashboard = useCallback(async () => {
    const userId = getStoredValue("userId");

    if (!userId) {
      setIsLoading(false);
      setStatusMessage("Please login to view your dashboard.");
      return;
    }

    setIsLoading(true);

    try {
      const response = await fetch(`/api/dashboard?userId=${userId}`);
      const data = (await response.json()) as Partial<DashboardData> & {
        message?: string;
      };

      if (!response.ok) {
        setStatusMessage(data.message ?? "Unable to load dashboard.");
        return;
      }

      setDashboard({
        latestVitals: data.latestVitals ?? null,
        vitalsHistory: data.vitalsHistory ?? [],
        upcomingAppointment: data.upcomingAppointment ?? null,
        medications: data.medications ?? [],
        reminders: data.reminders ?? [],
        medicalRecords: data.medicalRecords ?? [],
      });
    } catch {
      setStatusMessage("Unable to load dashboard. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const userId = getStoredValue("userId");

    if (!userId) {
      setTimeout(() => {
        setIsLoading(false);
        setStatusMessage("Please login to view your dashboard.");
      }, 0);
      return;
    }

    const controller = new AbortController();

    fetch(`/api/dashboard?userId=${userId}`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        const data = (await response.json()) as Partial<DashboardData> & {
          message?: string;
        };

        if (!response.ok) {
          setStatusMessage(data.message ?? "Unable to load dashboard.");
          return;
        }

        setDashboard({
          latestVitals: data.latestVitals ?? null,
          vitalsHistory: data.vitalsHistory ?? [],
          upcomingAppointment: data.upcomingAppointment ?? null,
          medications: data.medications ?? [],
          reminders: data.reminders ?? [],
          medicalRecords: data.medicalRecords ?? [],
        });
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }

        setStatusMessage("Unable to load dashboard. Please try again.");
      })
      .finally(() => {
        setIsLoading(false);
      });

    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      return;
    }

    if (Notification.permission !== "granted") {
      return;
    }

    const timers = dashboard.reminders
      .filter((reminder) => reminder.status === "UPCOMING")
      .map((reminder) => {
        const delay = new Date(reminder.dueAt).getTime() - Date.now();

        if (delay <= 0 || delay > 24 * 60 * 60 * 1000) {
          return null;
        }

        return window.setTimeout(() => {
          new Notification("Medicine reminder", {
            body: reminder.title,
          });
        }, delay);
      })
      .filter((timer): timer is number => timer !== null);

    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [dashboard.reminders]);

  const handleVitalsSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatusMessage("");
    const userId = getStoredValue("userId");

    if (!userId) {
      setStatusMessage("Please login before adding vitals.");
      return;
    }

    setIsSavingVitals(true);

    try {
      const response = await fetch("/api/vitals/add", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          userId,
          bloodPressure,
          sugarLevel,
        }),
      });

      const data = (await response.json()) as { message?: string };

      if (!response.ok) {
        setStatusMessage(data.message ?? "Unable to save vitals.");
        return;
      }

      setBloodPressure("");
      setSugarLevel("");
      setStatusMessage("Vitals saved and dashboard updated.");
      await loadDashboard();
    } catch {
      setStatusMessage("Unable to save vitals. Please try again.");
    } finally {
      setIsSavingVitals(false);
    }
  };

  const handleMedicineReminderSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatusMessage("");
    const userId = getStoredValue("userId");

    if (!userId) {
      setStatusMessage("Please login before adding a medicine reminder.");
      return;
    }

    if (!medicineReminderName.trim() || !medicineReminderAt) {
      setStatusMessage("Please enter medicine name and reminder time.");
      return;
    }

    setIsSavingMedicineReminder(true);

    try {
      if (typeof window !== "undefined" && "Notification" in window) {
        if (Notification.permission === "default") {
          await Notification.requestPermission();
        }
      }

      const response = await fetch("/api/reminders/add", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          userId,
          title: `Take ${medicineReminderName.trim()}`,
          dueAt: medicineReminderAt,
        }),
      });

      const data = (await response.json()) as { message?: string };

      if (!response.ok) {
        setStatusMessage(data.message ?? "Unable to save medicine reminder.");
        return;
      }

      setMedicineReminderName("");
      setMedicineReminderAt("");
      setStatusMessage("Medicine reminder saved. Browser notification will appear if permission is allowed.");
      await loadDashboard();
    } catch {
      setStatusMessage("Unable to save medicine reminder. Please try again.");
    } finally {
      setIsSavingMedicineReminder(false);
    }
  };

  const scanRecord = async (fileName: string, imageData: string, extractedText?: string) => {
    setStatusMessage("");

    const userId = getStoredValue("userId");

    if (!userId) {
      setStatusMessage("Please login before uploading records.");
      return;
    }

    setIsUploadingRecord(true);

    try {
      const trimmedExtractedText = extractedText?.trim();
      const response = await fetch("/api/medical-records/scan", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          userId,
          fileName,
          imageData,
          ...(trimmedExtractedText ? { extractedText: trimmedExtractedText } : {}),
        }),
      });

      const data = (await response.json()) as { message?: string };

      if (!response.ok) {
        setStatusMessage(data.message ?? "Unable to scan this record.");
        return;
      }

      setRecordFileName("");
      setRecordImageData("");
      setStatusMessage(data.message ?? "Report scanned and dashboard updated.");
      await loadDashboard();
    } catch {
      setStatusMessage("Unable to scan this record. Please try again.");
    } finally {
      setIsUploadingRecord(false);
    }
  };

  const handleRecordFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setRecordFileName(file.name);
    setStatusMessage("Preparing and compressing report image for scanning...");
    let preparedImageData = "";

    try {
      const imageData = await compressImageFile(file);
      preparedImageData = imageData;
      setRecordImageData(imageData);
      setStatusMessage("Sending report to secure OCR service...");
      await scanRecord(file.name, imageData);
    } catch {
      if (preparedImageData) {
        await scanRecord(file.name, preparedImageData);
        return;
      }

      setStatusMessage("Unable to read this image. Please try another photo.");
    }
  };

  const handleRecordSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatusMessage("");
    const userId = getStoredValue("userId");

    if (!userId) {
      setStatusMessage("Please login before uploading records.");
      return;
    }

    if (!recordImageData || !recordFileName) {
      setStatusMessage("Please upload a medicine, prescription, or lab report photo first.");
      return;
    }

    await scanRecord(recordFileName, recordImageData);
  };

  return (
    <main className="app-shell px-4 py-8 sm:px-6 lg:px-8">
      <section className="mx-auto max-w-7xl">
        <div className="dashboard-topbar flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <Link href="/" className="section-eyebrow">
              Nora MedLink
            </Link>
            <h1 className="section-title mt-3">
              Patient Dashboard
            </h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-slate-500">
              Vitals, records, reminders, and care alerts in one clean view.
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <Link href="/doctors" className="secondary-button">
              Find Doctors
            </Link>
            <Link href="/summarize" className="secondary-button">
              Summarize Report
            </Link>
            <Link href="/emergency" className="gradient-button">
              Emergency Visit
            </Link>
          </div>
        </div>

        {statusMessage ? (
          <p className="mb-6 rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm leading-6 text-blue-800">
            {statusMessage}
          </p>
        ) : null}

        <section className="premium-card dashboard-panel focus-band mb-6">
          <div className="relative flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-4">
              <CuteLogo type="records" size="sm" />
              <div>
                <p className="section-eyebrow">Doctor OTP</p>
                <h2 className="mt-2 text-xl font-black text-slate-950">
                  Share dashboard access
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  One use. 15 minute expiry.
                </p>
              </div>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <code className="rounded-2xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-center text-sm font-black tracking-[0.16em] text-emerald-800">
                {dashboardOtp?.code ?? "Generate OTP"}
              </code>
              <button
                type="button"
                onClick={generateDashboardOtp}
                disabled={isGeneratingOtp}
                className="gradient-button px-4 py-3"
              >
                {isGeneratingOtp ? "Generating..." : "Generate OTP"}
              </button>
              <button
                type="button"
                onClick={copyDashboardOtp}
                disabled={!dashboardOtp}
                className="secondary-button px-4 py-3"
              >
                Copy OTP
              </button>
            </div>
          </div>
          {dashboardOtp ? (
            <p className="relative mt-3 text-xs font-semibold text-emerald-700">
              Expires at {formatDate(dashboardOtp.expiresAt)}. After the doctor uses it, it cannot be used again.
            </p>
          ) : null}
        </section>

        <section className="health-hero section-lift mb-6 overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm shadow-slate-200/70">
          <div className="grid gap-0 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="relative overflow-hidden bg-slate-950 p-6 text-white sm:p-8">
              <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-teal-300 via-sky-300 to-indigo-300" />
              <div className="relative">
                <div className="flex items-center gap-4">
                  <CuteLogo type="vitals" size="lg" />
                  <p className="text-xs font-black uppercase tracking-[0.22em] text-white/75">
                    Current status
                  </p>
                </div>
                <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <h2 className="text-4xl font-black tracking-tight sm:text-5xl">
                      {healthStatus}
                    </h2>
                    <p className="mt-3 max-w-lg text-sm font-medium leading-6 text-white/75">
                      {primaryAlert}
                    </p>
                  </div>
                  <span
                    className={`w-fit rounded-full px-4 py-2 text-xs font-black uppercase tracking-[0.12em] shadow-lg ${
                      healthStatus === "Needs attention"
                        ? "bg-red-500 text-white shadow-red-900/20"
                        : "bg-white text-blue-700 shadow-blue-900/20"
                    }`}
                  >
                    {healthStatus === "Needs attention" ? "Review now" : "All clear"}
                  </span>
                </div>
              </div>
            </div>

            <div className="grid gap-3 bg-slate-50/70 p-5 sm:grid-cols-3 lg:grid-cols-1">
              <div className="metric-card">
                <div className="relative flex items-center gap-3">
                  <CuteLogo type="vitals" size="sm" />
                  <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">
                  Blood pressure
                  </p>
                </div>
                <p className="relative mt-2 text-2xl font-black text-slate-950">
                  {isLoading ? "Loading" : latestVitals?.bloodPressure ?? "No data"}
                </p>
              </div>
              <div className="metric-card border-emerald-100 bg-emerald-50/70">
                <div className="relative flex items-center gap-3">
                  <CuteLogo type="diabetes" size="sm" />
                  <p className="text-xs font-black uppercase tracking-[0.14em] text-emerald-600">
                  Sugar level
                  </p>
                </div>
                <p className="relative mt-2 text-2xl font-black text-slate-950">
                  {isLoading ? "Loading" : latestVitals?.sugarLevel ?? "No data"}
                </p>
              </div>
              <div className="metric-card border-blue-100 bg-blue-50/70">
                <div className="relative flex items-center gap-3">
                  <CuteLogo type="records" size="sm" />
                  <p className="text-xs font-black uppercase tracking-[0.14em] text-blue-600">
                  Records
                  </p>
                </div>
                <p className="relative mt-2 text-2xl font-black text-slate-950">
                  {dashboard.medicalRecords.length}
                </p>
              </div>
            </div>
          </div>
        </section>

        {alerts.length > 0 || problemTiles.length > 0 ? (
          <section className="premium-card mb-6 rounded-[24px] border border-red-100 bg-red-50 p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="relative flex items-center gap-3">
                  <div className="icon-3d flex h-12 w-12 items-center justify-center rounded-2xl bg-red-100 text-red-700">
                    <svg aria-hidden="true" className="h-6 w-6" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24">
                      <path d="M12 9v4" />
                      <path d="M12 17h.01" />
                      <path d="m10.3 3.9-8.2 14A2 2 0 0 0 3.8 21h16.4a2 2 0 0 0 1.7-3.1l-8.2-14a2 2 0 0 0-3.4 0Z" />
                    </svg>
                  </div>
                  <div>
                    <p className="text-xs font-black uppercase tracking-[0.16em] text-red-600">
                      Health problems to review
                    </p>
                    <h2 className="mt-2 text-xl font-black text-slate-950">
                      Attention needed
                    </h2>
                  </div>
                </div>
              </div>
              <span className="rounded-full bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.12em] text-red-700">
                {alerts.length + problemTiles.length} items
              </span>
            </div>
            <div className="relative mt-4 grid gap-3 md:grid-cols-2">
              {alerts.map((alert) => (
                <div
                  key={alert}
                  className="rounded-2xl border border-red-100 bg-white px-4 py-3 text-sm font-semibold leading-6 text-red-800 shadow-sm transition hover:-translate-y-0.5"
                >
                  {alert}
                </div>
              ))}
              {problemTiles.map((tile) => (
                <button
                  type="button"
                  key={tile.id}
                  onClick={() => openMedicalTile(tile.id)}
                className="rounded-2xl border border-red-100 bg-white px-4 py-3 text-left text-sm font-semibold leading-6 text-red-800 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
                >
                  {tile.title}: {tile.problemLabel || "Report needs attention."}
                </button>
              ))}
            </div>
          </section>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[1.45fr_0.9fr]">
          <section className="space-y-6">
            <div className="grid gap-5 md:grid-cols-2">
              <article className="premium-card metric-card">
                <div className="relative flex items-start justify-between gap-4">
                  <div>
                    <p className="section-eyebrow">Blood Pressure</p>
                    <p className="mt-5 text-4xl font-black text-slate-950">
                      {isLoading ? "Loading" : latestVitals?.bloodPressure ?? "No data"}
                    </p>
                  </div>
                  <CuteLogo type="heart" />
                </div>
              </article>

              <article className="premium-card metric-card">
                <div className="relative flex items-start justify-between gap-4">
                  <div>
                    <p className="section-eyebrow">Sugar Level</p>
                    <p className="mt-5 text-4xl font-black text-slate-950">
                      {isLoading ? "Loading" : latestVitals?.sugarLevel ?? "No data"}
                    </p>
                  </div>
                  <CuteLogo type="diabetes" />
                </div>
              </article>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <article className="premium-card dashboard-panel">
                <div className="relative flex items-center gap-3">
                  <CuteLogo type="appointment" size="sm" />
                  <h2 className="text-xl font-black text-slate-950">
                    Upcoming Appointment
                  </h2>
                </div>
                {dashboard.upcomingAppointment ? (
                  <div className="relative mt-5 rounded-2xl bg-slate-50 p-4">
                    <p className="text-sm font-bold text-slate-950">
                      {dashboard.upcomingAppointment.doctorName}
                    </p>
                    <p className="mt-2 text-sm text-slate-500">
                      {formatDate(dashboard.upcomingAppointment.date)}
                    </p>
                  </div>
                ) : (
                  <p className="mt-5 text-sm leading-6 text-slate-500">
                    No upcoming appointment found.
                  </p>
                )}
              </article>

              <article className="premium-card dashboard-panel">
                <div className="relative flex items-center gap-3">
                  <CuteLogo type="reminder" size="sm" />
                  <h2 className="text-xl font-black text-slate-950">
                    Upcoming Reminders
                  </h2>
                </div>
                <div className="relative mt-5 space-y-3">
                  {dashboard.reminders.length > 0 ? (
                    dashboard.reminders.map((reminder) => (
                      <div key={reminder.id} className="rounded-2xl bg-slate-50 p-4">
                        <p className="text-sm font-bold text-slate-950">
                          {reminder.title}
                        </p>
                        <p className="mt-2 text-xs font-medium text-slate-500">
                          {formatDate(reminder.dueAt)} - {reminder.status}
                        </p>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm leading-6 text-slate-500">
                      No upcoming reminders.
                    </p>
                  )}
                </div>
              </article>
            </div>

            <article className="premium-card dashboard-panel border-violet-100">
              <div className="relative flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex items-start gap-4">
                  <CuteLogo type="brain" />
                  <div>
                    <p className="section-eyebrow">Predictive Analysis</p>
                    <h2 className="mt-2 text-2xl font-black text-slate-950">
                      Risk Signals
                    </h2>
                    <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
                      Vitals and scanned reports, summarized.
                    </p>
                  </div>
                </div>
                <span className="rounded-full bg-violet-50 px-4 py-2 text-xs font-black uppercase tracking-[0.12em] text-violet-700">
                  AI assist
                </span>
              </div>

              <div className="relative mt-6 grid gap-4 md:grid-cols-2">
                {patientRisks.map((risk) => (
                  <button
                    type="button"
                    key={`${risk.id}-${risk.title}`}
                    onClick={() => openRisk(risk.id)}
                    className={`rounded-[24px] border p-4 text-left transition hover:-translate-y-0.5 hover:shadow-lg ${
                      risk.level === "High"
                        ? "border-red-100 bg-red-50"
                        : risk.level === "Moderate"
                          ? "border-amber-100 bg-amber-50"
                          : "border-blue-100 bg-blue-50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <CuteLogo type={risk.id} size="sm" />
                        <div>
                          <h3 className="text-sm font-black text-slate-950">
                            {risk.title}
                          </h3>
                          <p className="mt-1 text-xs font-semibold text-slate-500">
                            {risk.level} risk signal
                          </p>
                        </div>
                      </div>
                      <span
                        className={`rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-[0.1em] ${
                          risk.level === "High"
                            ? "bg-red-600 text-white"
                            : risk.level === "Moderate"
                              ? "bg-amber-500 text-white"
                              : "bg-white text-blue-700"
                        }`}
                      >
                        {risk.level}
                      </span>
                    </div>

                    <p className="mt-4 text-sm font-semibold leading-6 text-slate-800">
                      {risk.summary}
                    </p>
                    <p className="mt-3 rounded-xl bg-white/80 px-3 py-2 text-center text-xs font-black text-slate-700 shadow-sm">
                      View details
                    </p>
                  </button>
                ))}
              </div>
            </article>

            <article className="premium-card dashboard-panel">
              <div className="relative flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="section-eyebrow">Medical History</p>
                  <h2 className="mt-2 text-2xl font-black text-slate-950">
                    Medical History
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Organized by body system.
                  </p>
                </div>
                <span className="rounded-full bg-slate-100 px-4 py-2 text-xs font-black uppercase tracking-[0.14em] text-slate-500">
                  {dashboard.medicalRecords.length} records
                </span>
              </div>

              <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {medicalHistoryTiles.map((tile) => (
                  <button
                    type="button"
                    key={tile.id}
                    onClick={() => openMedicalTile(tile.id)}
                    className={`medical-tile group relative min-h-[160px] overflow-hidden rounded-2xl border p-5 text-left ${
                      activeMedicalTileId === tile.id
                        ? "medical-tile-active scale-[1.01]"
                        : "shadow-sm hover:-translate-y-0.5 hover:shadow-md"
                    } ${
                      tile.hasProblem
                        ? "medical-tile-alert border-red-200 bg-red-50"
                        : activeMedicalTileId === tile.id
                          ? "border-blue-200 bg-blue-50"
                          : "border-slate-100 bg-slate-50/80 hover:border-blue-100 hover:bg-white"
                    }`}
                  >
                    <div
                      className={`absolute -right-4 -top-4 h-20 w-20 rounded-full blur-2xl ${
                        tile.hasProblem ? "bg-red-200/70" : "bg-blue-100/70"
                      }`}
                    />
                    <div className="relative flex items-start justify-between gap-3">
                      <div className="medical-tile-icon shrink-0 transition duration-300">
                        <CuteLogo type={tile.id} />
                      </div>
                      {tile.hasProblem ? (
                        <span className="rounded-full bg-red-600 px-3 py-1 text-[10px] font-black uppercase tracking-[0.1em] text-white">
                          Alert
                        </span>
                      ) : (
                        <span className="rounded-full bg-white px-3 py-1 text-[10px] font-black uppercase tracking-[0.1em] text-slate-500 shadow-sm">
                          Stable
                        </span>
                      )}
                    </div>
                    <div className="relative mt-4">
                      <h3 className="text-xl font-black text-slate-950">
                        {tile.title}
                      </h3>
                      <p
                        className={`mt-2 w-fit rounded-full px-3 py-1 text-[10px] font-black uppercase tracking-[0.1em] ${
                          tile.hasProblem
                            ? "bg-red-600 text-white"
                            : "bg-white text-blue-700"
                        }`}
                      >
                        {getBodyFocusLabel(tile.id)}
                      </p>
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">
                        {tile.records.length > 0 ? tile.latestSummary : tile.description}
                      </p>
                    </div>
                    <div className="relative mt-4 flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-500">
                        Saved files
                      </span>
                      <span className="text-2xl font-black text-slate-950">
                        {tile.records.length}
                      </span>
                    </div>
                    <div className="relative mt-3 rounded-xl bg-white/80 px-3 py-2 text-center text-xs font-black text-slate-700 shadow-sm">
                      {tile.hasProblem ? "View problem" : "View history"}
                    </div>
                  </button>
                ))}
              </div>
            </article>

            <article className="premium-card dashboard-panel">
              <div className="relative flex items-center gap-3">
                <CuteLogo type="vitals" size="sm" />
                <h2 className="text-xl font-black text-slate-950">
                  Health Trends
                </h2>
              </div>
              <p className="relative mt-2 text-sm text-slate-500">Last 5 readings.</p>
              <div className="relative mt-5 overflow-x-auto">
                <table className="w-full min-w-[620px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-xs uppercase tracking-[0.14em] text-slate-400">
                      <th className="py-3 pr-4">Date</th>
                      <th className="py-3 pr-4">Blood Pressure</th>
                      <th className="py-3 pr-4">Sugar Level</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dashboard.vitalsHistory.length > 0 ? (
                      dashboard.vitalsHistory.map((vital) => (
                        <tr key={vital.id} className="border-b border-slate-100 last:border-0">
                          <td className="py-4 pr-4 text-slate-500">
                            {formatDate(vital.createdAt)}
                          </td>
                          <td className="py-4 pr-4 font-semibold text-slate-950">
                            {vital.bloodPressure}
                          </td>
                          <td className="py-4 pr-4 font-semibold text-slate-950">
                            {vital.sugarLevel}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="py-5 text-slate-500" colSpan={3}>
                          No vitals records yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </article>
          </section>

          <aside className="space-y-6">
            <form className="premium-card dashboard-panel" onSubmit={handleVitalsSubmit}>
              <div className="relative flex items-center gap-3">
                <CuteLogo type="vitals" size="sm" />
                <h2 className="text-xl font-black text-slate-950">Add Vitals</h2>
              </div>
              <div className="relative mt-5 space-y-4">
                <div>
                  <label htmlFor="bloodPressure" className="text-sm font-medium text-slate-700">
                    Blood Pressure
                  </label>
                  <input
                    id="bloodPressure"
                    value={bloodPressure}
                    onChange={(event) => setBloodPressure(event.target.value)}
                    className="form-input"
                    placeholder="120/80 mmHg"
                  />
                </div>
                <div>
                  <label htmlFor="sugarLevel" className="text-sm font-medium text-slate-700">
                    Sugar Level
                  </label>
                  <input
                    id="sugarLevel"
                    value={sugarLevel}
                    onChange={(event) => setSugarLevel(event.target.value)}
                    className="form-input"
                    placeholder="110 mg/dL"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isSavingVitals}
                  className="gradient-button w-full"
                >
                  {isSavingVitals ? "Saving..." : "Save Vitals"}
                </button>
              </div>
            </form>

            <article className="premium-card dashboard-panel border-emerald-100">
              <div className="relative flex items-start gap-4">
                <CuteLogo type="medicine" size="sm" />
                <div>
                  <h2 className="text-xl font-black text-slate-950">
                    Medicine Reminder
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Add the next dose time.
                  </p>
                </div>
              </div>

              <form className="relative mt-5 space-y-4" onSubmit={handleMedicineReminderSubmit}>
                <div>
                  <label htmlFor="medicineReminderName" className="text-sm font-medium text-slate-700">
                    Medicine Name
                  </label>
                  <input
                    id="medicineReminderName"
                    value={medicineReminderName}
                    onChange={(event) => setMedicineReminderName(event.target.value)}
                    className="form-input"
                    placeholder="Panadol, Insulin, Metformin..."
                  />
                </div>
                <div>
                  <label htmlFor="medicineReminderAt" className="text-sm font-medium text-slate-700">
                    Reminder Date & Time
                  </label>
                  <input
                    id="medicineReminderAt"
                    type="datetime-local"
                    value={medicineReminderAt}
                    onChange={(event) => setMedicineReminderAt(event.target.value)}
                    className="form-input"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isSavingMedicineReminder}
                  className="gradient-button w-full"
                >
                  {isSavingMedicineReminder ? "Saving reminder..." : "Add Medicine Alert"}
                </button>
              </form>

              <div className="relative mt-6 space-y-3">
                <h3 className="text-sm font-black uppercase tracking-[0.14em] text-slate-400">
                  Current Medications
                </h3>
                {dashboard.medications.length > 0 ? (
                  dashboard.medications.map((medication) => (
                    <div
                      key={medication.id}
                      className="flex items-center justify-between gap-4 rounded-2xl bg-slate-50 p-4"
                    >
                      <div>
                        <p className="text-sm font-bold text-slate-950">
                          {medication.name}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {medication.dosage}
                        </p>
                      </div>
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-bold ${
                          medication.status === "TAKEN"
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-amber-50 text-amber-700"
                        }`}
                      >
                        {medication.status.toLowerCase()}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="text-sm leading-6 text-slate-500">
                    No medicines added yet.
                  </p>
                )}
              </div>
            </article>

            <article className="premium-card dashboard-panel border-teal-100 bg-teal-50/60">
              <div className="relative flex items-start gap-4">
                <CuteLogo type="brain" size="sm" />
                <div>
                  <p className="section-eyebrow">AI Summary</p>
                  <h2 className="mt-2 text-xl font-black text-slate-950">
                    Medical Text Summarizer
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Generate a summary from your saved report text.
                  </p>
                </div>
              </div>
              <Link href="/summarize" className="gradient-button relative mt-5 w-full">
                Open Summarizer
              </Link>
            </article>

            <article className="premium-card overflow-hidden rounded-2xl border border-blue-100 bg-white shadow-sm shadow-blue-100/60">
              <div className="relative overflow-hidden bg-slate-950 p-6 text-white">
                <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-sky-300 to-teal-300" />
                <div className="flex items-start gap-4">
                  <CuteLogo type="scanner" />
                  <div className="relative">
                    <p className="text-xs font-black uppercase tracking-[0.16em] text-white/75">
                      Reports
                    </p>
                    <h2 className="mt-1 text-xl font-black text-white">
                      Upload & Scan
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-white/85">
                      Reports are sorted automatically.
                    </p>
                  </div>
                </div>
              </div>
              <div className="p-6">
                <form className="space-y-4" onSubmit={handleRecordSubmit}>
                  <label className="scanner-dropzone flex w-full cursor-pointer flex-col items-center justify-center gap-3 rounded-[24px] border border-dashed border-blue-300 bg-blue-50 px-5 py-6 text-center text-sm font-black text-blue-700 transition hover:border-blue-400 hover:bg-blue-100">
                    <svg
                      aria-hidden="true"
                      className="h-8 w-8"
                      fill="none"
                      stroke="currentColor"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      viewBox="0 0 24 24"
                    >
                      <path d="M12 16V4" />
                      <path d="m7 9 5-5 5 5" />
                      <path d="M20 16v4H4v-4" />
                    </svg>
                    <span>Choose Photo</span>
                    <input
                      type="file"
                      accept="image/*"
                      capture="environment"
                      className="hidden"
                      onChange={handleRecordFileChange}
                    />
                  </label>
                  {recordFileName ? (
                    <p className="rounded-2xl bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-600">
                      Selected: {recordFileName}
                    </p>
                  ) : null}
                  <button
                    type="submit"
                    disabled={isUploadingRecord}
                    className="gradient-button w-full"
                  >
                    {isUploadingRecord ? "Scanning..." : "Scan Selected Photo"}
                  </button>
                </form>

                <div className="mt-5 rounded-2xl bg-slate-50 px-4 py-3 text-center text-sm font-semibold text-slate-500">
                  {dashboard.medicalRecords.length} report photo(s) saved
                </div>
                {dashboard.medicalRecords.length > 0 ? (
                  <button
                    type="button"
                    onClick={() => openUploadDetails()}
                    className="secondary-button mt-3 w-full"
                  >
                    View latest upload details
                  </button>
                ) : null}
              </div>
            </article>
          </aside>
        </div>
      </section>

      {isMedicalTileOpen ? (
        <div className="fixed inset-0 z-50 flex items-end bg-slate-950/45 px-4 py-4 backdrop-blur-sm sm:items-center sm:justify-center">
          <button
            type="button"
            aria-label="Close medical history details"
            className="absolute inset-0 cursor-default"
            onClick={() => setIsMedicalTileOpen(false)}
          />
          <section
            key={activeMedicalTile.id}
            className={`medical-detail-panel relative max-h-[88vh] w-full overflow-y-auto rounded-[28px] border p-5 shadow-2xl sm:max-w-2xl ${
              activeMedicalTile.hasProblem
                ? "border-red-200 bg-red-50"
                : "border-blue-100 bg-blue-50"
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <CuteLogo type={activeMedicalTile.id} />
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">
                    Medical tile
                  </p>
                  <h3 className="mt-1 text-2xl font-black text-slate-950">
                    {activeMedicalTile.title}
                  </h3>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsMedicalTileOpen(false)}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-xl font-black text-slate-500 shadow-sm transition hover:text-slate-950"
                aria-label="Close"
              >
                x
              </button>
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <span
                className={`rounded-full px-4 py-2 text-xs font-black uppercase tracking-[0.12em] ${
                  activeMedicalTile.hasSeriousThreat
                    ? "bg-red-700 text-white"
                    : activeMedicalTile.hasProblem
                    ? "bg-red-600 text-white"
                    : "bg-white text-blue-700"
                }`}
              >
                {activeMedicalTile.hasSeriousThreat
                  ? "Serious alert"
                  : activeMedicalTile.hasProblem
                    ? "Needs attention"
                    : "Stable"}
              </span>
              <span className="rounded-full bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.12em] text-slate-600">
                {activeMedicalTile.records.length} saved files
              </span>
            </div>

            {activeMedicalTile.hasProblem ? (
              <div className="mt-5 rounded-2xl border border-red-100 bg-white p-4">
                <p className="text-xs font-black uppercase tracking-[0.14em] text-red-600">
                  Problem View
                </p>
                <p className="mt-2 text-sm font-semibold leading-6 text-slate-800">
                  {activeMedicalTile.problemLabel || "This section has a health concern."}
                </p>
                {activeProblemRecords.length > 0 ? (
                  <div className="mt-3 space-y-2">
                    {activeProblemRecords.map((record) => (
                      <p
                        key={record.id}
                        className="rounded-xl bg-red-50 px-3 py-2 text-xs font-semibold leading-5 text-red-800"
                      >
                        {record.title}: {getRecordSummary(record)}
                      </p>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-xs font-semibold leading-5 text-red-800">
                    The latest vitals are outside the normal range.
                  </p>
                )}
              </div>
            ) : (
              <p className="mt-5 rounded-2xl bg-white px-4 py-3 text-sm font-semibold leading-6 text-blue-800">
                No current alert for this tile.
              </p>
            )}

            {activeMedicalTile.hasSeriousThreat ? (
              <div className="mt-5 rounded-2xl border border-red-200 bg-red-600 p-4 text-white shadow-lg shadow-red-200">
                <p className="text-xs font-black uppercase tracking-[0.14em] text-red-100">
                  Serious Threat Alert
                </p>
                <div className="mt-3 space-y-2">
                  {activeMedicalTile.records.filter(recordHasSeriousThreat).map((record) => (
                    <p
                      key={record.id}
                      className="rounded-xl bg-white/15 px-3 py-2 text-sm font-bold leading-6"
                    >
                      {record.title}: {getSeriousThreatAlert(record)}
                    </p>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="mt-5 space-y-3">
              {activeMedicalTile.records.length > 0 ? (
                activeMedicalTile.records.map((record) => (
                  <div
                    key={record.id}
                    className="rounded-2xl border border-white bg-white p-4 shadow-sm"
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-sm font-black text-slate-950">
                          {record.title}
                        </p>
                        <p className="mt-1 text-xs font-semibold text-slate-500">
                          {record.fileName}
                        </p>
                      </div>
                      {recordHasProblem(record) ? (
                        <span className="w-fit rounded-full bg-red-50 px-3 py-1 text-[10px] font-black uppercase tracking-[0.1em] text-red-700">
                          {recordHasSeriousThreat(record) ? "Serious alert" : "Problem found"}
                        </span>
                      ) : null}
                    </div>
                    {recordHasSeriousThreat(record) ? (
                      <div className="mt-3 rounded-2xl border border-red-100 bg-red-50 px-4 py-3">
                        <p className="text-xs font-black uppercase tracking-[0.14em] text-red-700">
                          Serious Threat Alert
                        </p>
                        <p className="mt-2 text-sm font-bold leading-6 text-red-900">
                          {getSeriousThreatAlert(record)}
                        </p>
                      </div>
                    ) : null}
                    <p className="mt-3 text-xs leading-5 text-slate-600">
                      {getRecordSummary(record)}
                    </p>
                    {record.imageUrl ? (
                      <div className="mt-4 rounded-2xl border border-slate-100 bg-slate-50 p-3">
                        <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">
                          Scanned report picture
                        </p>
                        <div
                          className="mt-3 h-[420px] rounded-xl border border-white bg-white bg-contain bg-center bg-no-repeat shadow-inner"
                          style={getRecordImageStyle(record)}
                          aria-label={`Full scanned lab report image for ${record.title}`}
                          role="img"
                        />
                      </div>
                    ) : null}
                    <p className="mt-3 text-[11px] font-semibold text-slate-400">
                      {formatDate(record.createdAt)}
                    </p>
                    <button
                      type="button"
                      onClick={() => deleteMedicalRecord(record.id)}
                      disabled={deletingRecordId === record.id}
                      className="mt-3 rounded-full bg-red-50 px-4 py-2 text-xs font-black text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {deletingRecordId === record.id ? "Removing..." : "Remove report"}
                    </button>
                  </div>
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-white bg-white/70 px-4 py-6 text-center">
                  <p className="text-sm font-bold text-slate-700">
                    No files saved in this tile yet.
                  </p>
                  <p className="mt-2 text-xs leading-5 text-slate-500">
                    Upload a report or prescription photo from the scanner card.
                  </p>
                </div>
              )}
            </div>
          </section>
        </div>
      ) : null}

      {isRiskOpen ? (
        <div className="fixed inset-0 z-50 flex items-end bg-slate-950/45 px-4 py-4 backdrop-blur-sm sm:items-center sm:justify-center">
          <button
            type="button"
            aria-label="Close prediction details"
            className="absolute inset-0 cursor-default"
            onClick={() => setIsRiskOpen(false)}
          />
          <section
            className={`medical-detail-panel relative max-h-[88vh] w-full overflow-y-auto rounded-[28px] border p-5 shadow-2xl sm:max-w-xl ${
              activeRisk.level === "High"
                ? "border-red-200 bg-red-50"
                : activeRisk.level === "Moderate"
                  ? "border-amber-200 bg-amber-50"
                  : "border-blue-100 bg-blue-50"
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <CuteLogo type={activeRisk.id} />
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">
                    Prediction details
                  </p>
                  <h3 className="mt-1 text-2xl font-black text-slate-950">
                    {activeRisk.title}
                  </h3>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsRiskOpen(false)}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-xl font-black text-slate-500 shadow-sm transition hover:text-slate-950"
                aria-label="Close"
              >
                x
              </button>
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <span
                className={`rounded-full px-4 py-2 text-xs font-black uppercase tracking-[0.12em] ${
                  activeRisk.level === "High"
                    ? "bg-red-600 text-white"
                    : activeRisk.level === "Moderate"
                      ? "bg-amber-500 text-white"
                      : "bg-white text-blue-700"
                }`}
              >
                {activeRisk.level} risk signal
              </span>
              <span className="rounded-full bg-white px-4 py-2 text-xs font-black uppercase tracking-[0.12em] text-slate-600">
                Not a diagnosis
              </span>
            </div>

            <p className="mt-5 rounded-2xl bg-white px-4 py-3 text-sm font-semibold leading-6 text-slate-800">
              {activeRisk.summary}
            </p>

            <div className="mt-4 space-y-2">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">
                Evidence
              </p>
              {activeRisk.evidence.map((item) => (
                <p
                  key={item}
                  className="rounded-xl bg-white/80 px-3 py-2 text-xs font-semibold leading-5 text-slate-600"
                >
                  {item}
                </p>
              ))}
            </div>

            <p className="mt-4 rounded-2xl bg-white px-4 py-3 text-sm font-bold leading-6 text-slate-800">
              Next step: {activeRisk.action}
            </p>
          </section>
        </div>
      ) : null}

      {isUploadDetailsOpen && activeUploadRecord ? (
        <div className="fixed inset-0 z-50 flex items-end bg-slate-950/45 px-4 py-4 backdrop-blur-sm sm:items-center sm:justify-center">
          <button
            type="button"
            aria-label="Close upload details"
            className="absolute inset-0 cursor-default"
            onClick={() => setIsUploadDetailsOpen(false)}
          />
          <section className="medical-detail-panel relative max-h-[88vh] w-full overflow-y-auto rounded-[28px] border border-blue-100 bg-blue-50 p-5 shadow-2xl sm:max-w-xl">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <CuteLogo type="scanner" />
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-500">
                    Upload details
                  </p>
                  <h3 className="mt-1 text-2xl font-black text-slate-950">
                    {activeUploadRecord.title}
                  </h3>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsUploadDetailsOpen(false)}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-xl font-black text-slate-500 shadow-sm transition hover:text-slate-950"
                aria-label="Close"
              >
                x
              </button>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl bg-white px-4 py-3">
                <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">
                  File
                </p>
                <p className="mt-1 text-sm font-bold text-slate-800">
                  {activeUploadRecord.fileName}
                </p>
              </div>
              <div className="rounded-2xl bg-white px-4 py-3">
                <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">
                  Scan status
                </p>
                <p className="mt-1 text-sm font-bold text-slate-800">
                  {activeUploadRecord.scanStatus ?? "Saved"}
                </p>
              </div>
            </div>

            <div className="mt-4 rounded-2xl bg-white px-4 py-3">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">
                Uploaded
              </p>
              <p className="mt-1 text-sm font-bold text-slate-800">
                {formatDate(activeUploadRecord.createdAt)}
              </p>
            </div>

            <div className="mt-4 rounded-2xl bg-white px-4 py-4">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">
                Clear report summary
              </p>
              <p className="mt-3 whitespace-pre-wrap text-sm font-semibold leading-6 text-slate-700">
                {activeUploadRecord.extractedText &&
                !isLegacyScannerSetupText(activeUploadRecord.extractedText)
                  ? activeUploadRecord.extractedText
                  : "No readable text was found yet. Try uploading a clearer photo."}
              </p>
            </div>

            {activeUploadRecord.imageUrl ? (
              <div className="mt-4 rounded-2xl bg-white px-4 py-4">
                <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">
                  Scanned report picture
                </p>
                <div
                  className="mt-3 h-72 rounded-2xl border border-slate-100 bg-slate-100 bg-contain bg-center bg-no-repeat shadow-inner"
                  style={getRecordImageStyle(activeUploadRecord)}
                  aria-label={`Scanned lab report image for ${activeUploadRecord.title}`}
                  role="img"
                />
              </div>
            ) : null}
          </section>
        </div>
      ) : null}
    </main>
  );
}

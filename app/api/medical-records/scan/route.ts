import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";

type ScanBody = {
  extractedText?: string;
  userId: number | string;
  fileName: string;
  imageData?: string;
  imageUrl?: string;
};

const medicalRecordSelect = {
  id: true,
  userId: true,
  title: true,
  fileName: true,
  imageUrl: true,
  extractedText: true,
  scanStatus: true,
  createdAt: true,
};

function isValidImageSource(value: unknown): value is string {
  return (
    typeof value === "string" &&
    (value.startsWith("data:image/") || value.startsWith("https://"))
  );
}

function isScanBody(value: unknown): value is ScanBody {
  if (!value || typeof value !== "object") {
    return false;
  }

  const body = value as Record<string, unknown>;

  return (
    (typeof body.userId === "number" || typeof body.userId === "string") &&
    typeof body.fileName === "string" &&
    body.fileName.trim().length > 0 &&
    (typeof body.extractedText === "undefined" || typeof body.extractedText === "string") &&
    (isValidImageSource(body.imageData) || isValidImageSource(body.imageUrl))
  );
}

function fallbackTitle(fileName: string) {
  return fileName.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ") || "Scanned report";
}

function cleanMedicalText(text: string) {
  const normalized = text
    .replace(/\s+/g, " ")
    .replace(/\s*([:;,./-])\s*/g, "$1 ")
    .trim();

  if (!normalized) {
    return "";
  }

  return normalized.length > 4000 ? `${normalized.slice(0, 4000).trimEnd()}...` : normalized;
}

function uniqueValues(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function getImportantFindings(text: string) {
  const normalizedText = text.toLowerCase();
  const findingPatterns = [
    "hb",
    "hemoglobin",
    "haemoglobin",
    "wbc",
    "rbc",
    "platelet",
    "glucose",
    "sugar",
    "hba1c",
    "cholesterol",
    "ldl",
    "hdl",
    "triglyceride",
    "creatinine",
    "urea",
    "uric acid",
    "bilirubin",
    "sgpt",
    "sgot",
    "alt",
    "ast",
    "calcium",
    "vitamin d",
    "tsh",
  ];
  const findings: string[] = [];

  for (const pattern of findingPatterns) {
    const escapedPattern = pattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const match = text.match(new RegExp(`\\b${escapedPattern}\\b[^,.;\\n]{0,45}`, "i"));

    if (match && normalizedText.includes(pattern)) {
      findings.push(match[0].replace(/\s+/g, " ").trim());
    }
  }

  return uniqueValues(findings).slice(0, 6);
}

function getReportType(text: string, fileName: string) {
  const searchText = `${fileName} ${text}`.toLowerCase();

  if (/\b(cbc|hemoglobin|haemoglobin|platelet|wbc|rbc)\b/.test(searchText)) {
    return "CBC or blood test report";
  }

  if (/\b(hba1c|glucose|sugar|diabetes|diabetic)\b/.test(searchText)) {
    return "diabetes or glucose report";
  }

  if (/\b(lft|bilirubin|sgpt|sgot|alt|ast|alkaline phosphatase)\b/.test(searchText)) {
    return "liver function report";
  }

  if (/\b(kft|rft|creatinine|urea|renal|kidney|egfr)\b/.test(searchText)) {
    return "kidney function report";
  }

  if (/\b(lipid|cholesterol|ldl|hdl|triglyceride)\b/.test(searchText)) {
    return "heart or lipid report";
  }

  return "medical lab report";
}

function hasNearbyWords(text: string, medicalWords: string[], concernWords: string[]) {
  const normalizedText = text.toLowerCase();

  return medicalWords.some((medicalWord) =>
    concernWords.some((concernWord) => {
      const medicalPattern = medicalWord.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const concernPattern = concernWord.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const nearbyPattern = new RegExp(
        `(?:\\b${medicalPattern}\\b.{0,80}\\b${concernPattern}\\b|\\b${concernPattern}\\b.{0,80}\\b${medicalPattern}\\b)`,
        "i",
      );

      return nearbyPattern.test(normalizedText);
    }),
  );
}

type LabProblemRule = {
  aliases: string[];
  displayName: string;
  highText: string;
  lowText: string;
  highProblem?: boolean;
  lowProblem?: boolean;
  normalHigh?: number;
  normalLow?: number;
};

type LabProblem = {
  direction: "high" | "low" | "positive" | "abnormal";
  displayName: string;
  problemText: string;
  valueText: string;
};

const labProblemRules: LabProblemRule[] = [
  {
    aliases: ["glucose", "sugar", "fbs", "rbs", "fasting blood sugar", "random blood sugar"],
    displayName: "blood sugar",
    highText: "High blood sugar",
    lowText: "Low blood sugar",
    normalHigh: 140,
    normalLow: 70,
  },
  {
    aliases: ["hba1c", "hb a1c", "glycated hemoglobin"],
    displayName: "HbA1c",
    highText: "High long-term sugar level",
    lowText: "Low HbA1c",
    lowProblem: false,
    normalHigh: 5.7,
  },
  {
    aliases: ["hemoglobin", "haemoglobin", "hb"],
    displayName: "hemoglobin",
    highText: "High hemoglobin",
    lowText: "Low hemoglobin, which can suggest anemia",
    normalHigh: 17.5,
    normalLow: 12,
  },
  {
    aliases: ["wbc", "white blood cell", "white blood cells", "tlc"],
    displayName: "white blood cells",
    highText: "High white blood cells, which can suggest infection or inflammation",
    lowText: "Low white blood cells",
    normalHigh: 11000,
    normalLow: 4000,
  },
  {
    aliases: ["platelet", "platelets", "plt"],
    displayName: "platelets",
    highText: "High platelets",
    lowText: "Low platelets, which can increase bleeding or bruising risk",
    normalHigh: 450000,
    normalLow: 150000,
  },
  {
    aliases: ["creatinine"],
    displayName: "creatinine",
    highText: "High creatinine, which can suggest kidney stress",
    lowText: "Low creatinine",
    lowProblem: false,
    normalHigh: 1.3,
  },
  {
    aliases: ["urea", "blood urea", "bun"],
    displayName: "urea",
    highText: "High urea, which can suggest kidney or hydration problems",
    lowText: "Low urea",
    lowProblem: false,
    normalHigh: 45,
  },
  {
    aliases: ["bilirubin"],
    displayName: "bilirubin",
    highText: "High bilirubin, which can suggest a liver or jaundice-related issue",
    lowText: "Low bilirubin",
    lowProblem: false,
    normalHigh: 1.2,
  },
  {
    aliases: ["sgpt", "alt"],
    displayName: "ALT or SGPT",
    highText: "High ALT or SGPT, which can suggest liver irritation",
    lowText: "Low ALT or SGPT",
    lowProblem: false,
    normalHigh: 45,
  },
  {
    aliases: ["sgot", "ast"],
    displayName: "AST or SGOT",
    highText: "High AST or SGOT, which can suggest liver or muscle irritation",
    lowText: "Low AST or SGOT",
    lowProblem: false,
    normalHigh: 40,
  },
  {
    aliases: ["cholesterol", "total cholesterol"],
    displayName: "cholesterol",
    highText: "High cholesterol, which can affect heart health",
    lowText: "Low cholesterol",
    lowProblem: false,
    normalHigh: 200,
  },
  {
    aliases: ["ldl"],
    displayName: "LDL cholesterol",
    highText: "High LDL cholesterol, which can affect heart health",
    lowText: "Low LDL cholesterol",
    lowProblem: false,
    normalHigh: 100,
  },
  {
    aliases: ["hdl"],
    displayName: "HDL cholesterol",
    highText: "High HDL cholesterol",
    lowText: "Low HDL cholesterol",
    highProblem: false,
    normalLow: 40,
  },
  {
    aliases: ["triglyceride", "triglycerides"],
    displayName: "triglycerides",
    highText: "High triglycerides, which can affect heart health",
    lowText: "Low triglycerides",
    lowProblem: false,
    normalHigh: 150,
  },
  {
    aliases: ["tsh"],
    displayName: "TSH",
    highText: "High TSH, which can suggest low thyroid activity",
    lowText: "Low TSH, which can suggest high thyroid activity",
    normalHigh: 4.5,
    normalLow: 0.4,
  },
  {
    aliases: ["vitamin d", "25 oh vitamin d"],
    displayName: "vitamin D",
    highText: "High vitamin D",
    lowText: "Low vitamin D",
    highProblem: false,
    normalLow: 20,
  },
];

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function getLineValue(line: string) {
  const withoutDates = line.replace(/\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b/g, " ");
  const match = withoutDates.match(/[-+]?\d+(?:\.\d+)?/);

  return match ? Number(match[0]) : null;
}

function getValueNearAlias(text: string, alias: string) {
  const escapedAlias = escapeRegExp(alias);
  const afterAlias = text.match(
    new RegExp(`\\b${escapedAlias}\\b[^\\d<>+-]{0,35}[<>+-]?\\s*(\\d+(?:\\.\\d+)?)`, "i"),
  );

  if (afterAlias) {
    return Number(afterAlias[1]);
  }

  const beforeAlias = text.match(
    new RegExp(`(\\d+(?:\\.\\d+)?)[^a-zA-Z\\d]{0,20}\\b${escapedAlias}\\b`, "i"),
  );

  return beforeAlias ? Number(beforeAlias[1]) : null;
}

function getRuleValue(text: string, rule: LabProblemRule) {
  for (const alias of rule.aliases) {
    const value = getValueNearAlias(text, alias);

    if (value !== null && Number.isFinite(value)) {
      return value;
    }
  }

  return getLineValue(text);
}

function getReferenceRange(line: string) {
  const match = line.match(
    /(?:range|reference|normal|ref)?\s*:?\s*([-+]?\d+(?:\.\d+)?)\s*(?:-|to)\s*([-+]?\d+(?:\.\d+)?)/i,
  );

  if (!match) {
    return null;
  }

  const low = Number(match[1]);
  const high = Number(match[2]);

  if (!Number.isFinite(low) || !Number.isFinite(high) || low >= high) {
    return null;
  }

  return { low, high };
}

function getExplicitDirection(line: string) {
  if (/\b(high|raised|elevated|increased|critical high|above normal|abnormal high)\b/i.test(line)) {
    return "high" as const;
  }

  if (/\b(low|reduced|decreased|critical low|below normal|abnormal low)\b/i.test(line)) {
    return "low" as const;
  }

  if (/(?:^|\s|\()h(?:\s|\)|$)|\bflag\s*h\b/i.test(line)) {
    return "high" as const;
  }

  if (/(?:^|\s|\()l(?:\s|\)|$)|\bflag\s*l\b/i.test(line)) {
    return "low" as const;
  }

  return null;
}

function getLineDirection(line: string, rule?: LabProblemRule, valueOverride?: number | null) {
  const explicitDirection = getExplicitDirection(line);

  if (explicitDirection) {
    return explicitDirection;
  }

  const value = typeof valueOverride === "number" ? valueOverride : getLineValue(line);
  const range = getReferenceRange(line);

  if (value === null) {
    return null;
  }

  if (range && value > range.high) {
    return "high" as const;
  }

  if (range && value < range.low) {
    return "low" as const;
  }

  if (typeof rule?.normalHigh === "number" && value > rule.normalHigh) {
    return "high" as const;
  }

  if (typeof rule?.normalLow === "number" && value < rule.normalLow) {
    return "low" as const;
  }

  return null;
}

function formatProblemValue(line: string, displayName: string, valueOverride?: number | null) {
  const value = typeof valueOverride === "number" ? valueOverride : getLineValue(line);
  const range = getReferenceRange(line);
  const valuePart = value === null ? "" : `${displayName}: ${value}`;
  const rangePart = range ? `normal range ${range.low}-${range.high}` : "";

  if (valuePart && rangePart) {
    return `${valuePart}, ${rangePart}`;
  }

  return valuePart || line.replace(/\s+/g, " ").trim().slice(0, 90);
}

function getProblemSearchSegments(text: string) {
  const segments = text
    .split(/\r?\n| {2,}|\t+/)
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter((line) => line.length > 0);
  const compactText = text.replace(/\s+/g, " ").trim();

  for (const rule of labProblemRules) {
    for (const alias of rule.aliases) {
      const regex = new RegExp(`\\b${escapeRegExp(alias)}\\b`, "gi");
      let match = regex.exec(compactText);

      while (match) {
        const start = Math.max(0, match.index - 35);
        const end = Math.min(compactText.length, match.index + alias.length + 170);
        segments.push(compactText.slice(start, end).trim());
        match = regex.exec(compactText);
      }
    }
  }

  return uniqueValues(segments);
}

function getExtractedLabProblems(text: string) {
  const lines = getProblemSearchSegments(text);
  const problems: LabProblem[] = [];

  for (const line of lines) {
    for (const rule of labProblemRules) {
      const matchingAlias = rule.aliases.find((alias) =>
        new RegExp(`\\b${escapeRegExp(alias)}\\b`, "i").test(line),
      );

      if (!matchingAlias) {
        continue;
      }

      const value = getRuleValue(line, rule);
      const direction = getLineDirection(line, rule, value);

      if (!direction) {
        continue;
      }

      if (direction === "high" && rule.highProblem === false) {
        continue;
      }

      if (direction === "low" && rule.lowProblem === false) {
        continue;
      }

      problems.push({
        direction,
        displayName: rule.displayName,
        problemText: direction === "high" ? rule.highText : rule.lowText,
        valueText: formatProblemValue(line, rule.displayName, value),
      });
    }
  }

  if (/\bpositive\b/i.test(text)) {
    const positiveLine = lines.find((line) => /\bpositive\b/i.test(line));

    problems.push({
      direction: "positive",
      displayName: "test result",
      problemText: "A test result is positive",
      valueText: positiveLine ?? "positive result",
    });
  }

  return uniqueValues(
    problems.map((problem) => `${problem.problemText}${problem.valueText ? ` (${problem.valueText})` : ""}`),
  ).slice(0, 5);
}

function getProblemSummary(text: string) {
  const extractedLabProblems = getExtractedLabProblems(text);

  if (extractedLabProblems.length > 0) {
    return extractedLabProblems;
  }

  const concernWords = [
    "abnormal",
    "critical",
    "detected",
    "elevated",
    "high",
    "increased",
    "low",
    "positive",
    "raised",
    "reduced",
  ];
  const summaries: string[] = [];

  if (hasNearbyWords(text, ["glucose", "sugar", "hba1c"], ["elevated", "high", "raised", "increased"])) {
    summaries.push("Sugar control may need attention because the report mentions a high glucose or HbA1c reading.");
  }

  if (hasNearbyWords(text, ["hemoglobin", "haemoglobin", "hb"], ["low", "reduced"]) || /\banemia\b/i.test(text)) {
    summaries.push("Blood level may be low, which can point to anemia or weakness.");
  }

  if (hasNearbyWords(text, ["wbc", "white blood"], ["elevated", "high", "raised", "increased"])) {
    summaries.push("White blood cells may be raised, which can happen with infection or inflammation.");
  }

  if (hasNearbyWords(text, ["platelet", "platelets"], ["low", "reduced"])) {
    summaries.push("Platelets may be low, so bleeding or bruising risk should be reviewed by a clinician.");
  }

  if (hasNearbyWords(text, ["creatinine", "urea", "egfr", "kidney", "renal"], concernWords)) {
    summaries.push("Kidney function may need follow-up because kidney-related readings are marked outside the usual range.");
  }

  if (hasNearbyWords(text, ["bilirubin", "sgpt", "sgot", "alt", "ast", "liver", "lft"], concernWords)) {
    summaries.push("Liver-related readings may need follow-up because the report marks liver tests as outside the usual range.");
  }

  if (hasNearbyWords(text, ["cholesterol", "ldl", "triglyceride", "lipid"], ["elevated", "high", "raised", "increased"])) {
    summaries.push("Cholesterol or lipid levels may be high, which can affect heart health over time.");
  }

  if (/\bpositive\b/i.test(text) && summaries.length === 0) {
    summaries.push("The report includes a positive result. Please review what that test was for with a doctor.");
  }

  if (/\babnormal\b/i.test(text) && summaries.length === 0) {
    summaries.push("The report marks something as abnormal, but the exact problem is not clear from the scanned text.");
  }

  return uniqueValues(summaries).slice(0, 3);
}

function summarizeMedicalText(text: string, fileName: string) {
  const cleanText = cleanMedicalText(text);

  if (!cleanText) {
    return "No readable medical text was found in this image.";
  }

  const reportType = getReportType(cleanText, fileName);
  const findings = getImportantFindings(cleanText);
  const problemSummary = getProblemSummary(text);
  const readingsText =
    findings.length > 0 ? ` Readable readings include: ${findings.join("; ")}.` : "";

  if (problemSummary.length > 0) {
    return `Problem summary: This looks like a ${reportType}. Main concern: ${problemSummary.join(" ")}${readingsText} This is not a diagnosis; show the report to a doctor for confirmation.`;
  }

  if (!readingsText) {
    const shortText =
      cleanText.length > 260 ? `${cleanText.slice(0, 260).trimEnd()}...` : cleanText;

    return `Report summary: This looks like a ${reportType}. No clear problem was detected from the readable text. Scanned text: ${shortText}`;
  }

  return `Report summary: This looks like a ${reportType}. No clear problem was detected from the readable text.${readingsText}`;
}

function buildExtractedEntities(text: string) {
  return getImportantFindings(text).map((finding) => ({
    text: finding,
    label: "clinical_finding",
    confidence: 0.76,
  }));
}

function buildRuleWarnings(text: string) {
  const normalizedText = text.toLowerCase();
  const warnings: string[] = [];

  if (/\b(high|low|positive|abnormal|critical)\b/.test(normalizedText)) {
    warnings.push("Report text includes abnormal or flagged terms that require clinician review.");
  }

  if (getProblemSummary(text).length > 0) {
    warnings.push("Rule-based scan found possible lab value concerns.");
  }

  return warnings;
}

async function saveMedicalAiAnalysis(record: {
  id: number;
  userId: number;
  extractedText: string | null;
  scanStatus: string;
}) {
  const text = record.extractedText ?? "";
  const extractedEntities = buildExtractedEntities(text);

  await prisma.medicalAiAnalysis.create({
    data: {
      userId: record.userId,
      medicalRecordId: record.id,
      source: "next_scan_rule_based",
      extractedEntities,
      confidenceScore: extractedEntities.length > 0 ? 0.76 : 0.42,
      ruleWarnings: buildRuleWarnings(text),
      validationResults: {
        scanStatus: record.scanStatus,
        hasExtractedText: text.trim().length > 0,
      },
      doctorSummary: text || null,
    },
  });
}

async function findExistingImageRecord(userId: number, imageUrl: string) {
  const matchingRecords = await prisma.medicalRecord.findMany({
    where: { userId, imageUrl },
    orderBy: { createdAt: "asc" },
    select: medicalRecordSelect,
  });

  const [firstRecord, ...duplicateRecords] = matchingRecords;

  if (duplicateRecords.length > 0) {
    await prisma.medicalRecord.deleteMany({
      where: {
        id: { in: duplicateRecords.map((record) => record.id) },
      },
    });
  }

  return firstRecord ?? null;
}

async function findExistingSummaryRecord(userId: number, extractedText: string, fileName: string) {
  const matchingRecords = await prisma.medicalRecord.findMany({
    where: {
      userId,
      OR: [
        { extractedText },
        {
          fileName: fileName.trim(),
          extractedText,
        },
      ],
    },
    orderBy: { createdAt: "asc" },
    select: medicalRecordSelect,
  });

  const [firstRecord, ...duplicateRecords] = matchingRecords;

  if (duplicateRecords.length > 0) {
    await prisma.medicalRecord.deleteMany({
      where: {
        id: { in: duplicateRecords.map((record) => record.id) },
      },
    });
  }

  return firstRecord ?? null;
}

function getOcrSpaceApiKey() {
  return process.env.OCR_SPACE_API_KEY?.trim() || "";
}

function parseOcrSpaceText(response: unknown): string {
  if (!response || typeof response !== "object") {
    return "";
  }

  const body = response as {
    ParsedResults?: Array<{ ParsedText?: unknown }>;
    IsErroredOnProcessing?: unknown;
    ErrorMessage?: unknown;
    ErrorDetails?: unknown;
  };

  if (body.IsErroredOnProcessing) {
    const message = Array.isArray(body.ErrorMessage)
      ? body.ErrorMessage.join(" ")
      : body.ErrorMessage || body.ErrorDetails || "OCR.Space failed to process the report.";
    throw new Error(String(message));
  }

  return (body.ParsedResults ?? [])
    .map((result) => (typeof result.ParsedText === "string" ? result.ParsedText.trim() : ""))
    .filter(Boolean)
    .join("\n\n")
    .trim();
}

function dataUrlToBlob(imageData: string) {
  const match = imageData.match(/^data:([^;]+);base64,(.+)$/);
  if (!match) {
    return null;
  }

  const [, contentType, base64] = match;
  const bytes = Buffer.from(base64, "base64");
  return {
    blob: new Blob([bytes], { type: contentType }),
    contentType,
  };
}

async function callOcrSpace(imageUrl: string) {
  const apiKey = getOcrSpaceApiKey();
  if (!apiKey) {
    throw new Error("OCR_SPACE_API_KEY is missing.");
  }

  const endpoint = process.env.OCR_SPACE_API_URL?.trim() || "https://api.ocr.space/parse/image";
  const formData = new FormData();
  formData.set("apikey", apiKey);
  formData.set("language", process.env.OCR_SPACE_LANGUAGE?.trim() || "eng");
  formData.set("OCREngine", process.env.OCR_SPACE_ENGINE?.trim() || "2");
  formData.set("isTable", "true");
  formData.set("scale", "true");
  formData.set("detectOrientation", "true");

  if (imageUrl.startsWith("data:")) {
    if (!dataUrlToBlob(imageUrl)) {
      throw new Error("Invalid image data URL.");
    }
    formData.set("base64Image", imageUrl);
  } else {
    formData.set("url", imageUrl);
  }

  const response = await fetch(endpoint, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = new Error(`OCR.Space failed with status ${response.status}.`);
    (error as Error & { status?: number }).status = response.status;
    throw error;
  }

  const extractedText = parseOcrSpaceText(await response.json());
  if (!extractedText) {
    throw new Error("OCR.Space returned no readable text.");
  }

  return extractedText;
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isRetryableStatus(status: number) {
  return status === 429 || status === 500 || status === 502 || status === 503 || status === 504;
}

async function extractMedicalText(imageUrl: string) {
  const maxAttempts = 3;
  let lastError: unknown;

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      return await callOcrSpace(imageUrl);
    } catch (error) {
      lastError = error;
      const status = error instanceof Error ? (error as Error & { status?: number }).status : undefined;

      if (typeof status !== "number" || !isRetryableStatus(status) || attempt === maxAttempts) {
        throw error;
      }

      const delayMs = 500 * 2 ** (attempt - 1);
      await sleep(delayMs);
    }
  }

  throw lastError instanceof Error ? lastError : new Error("OCR.Space failed.");
}

export async function POST(request: Request) {
  const body: unknown = await request.json().catch(() => null);

  if (!isScanBody(body)) {
    return Response.json(
      { message: "User ID and a valid image are required." },
      { status: 400 },
    );
  }

  const userId = Number(body.userId);

  if (!Number.isInteger(userId) || userId <= 0) {
    return Response.json({ message: "Invalid user ID." }, { status: 400 });
  }

  const user = await prisma.user.findUnique({
    where: { id: userId },
    select: { id: true },
  });

  if (!user) {
    return Response.json({ message: "User not found." }, { status: 404 });
  }

  const imageUrl = body.imageData ?? body.imageUrl;

  if (!imageUrl) {
    return Response.json({ message: "Image is required." }, { status: 400 });
  }

  const existingImageRecord = await findExistingImageRecord(userId, imageUrl);

  if (existingImageRecord) {
    return Response.json(
      {
        message: "This lab report is already saved, so Nora removed duplicate copies and kept the original.",
        record: existingImageRecord,
        duplicate: true,
      },
      { status: 200 },
    );
  }

  const hasLocalText = typeof body.extractedText === "string";
  const localText = typeof body.extractedText === "string" ? body.extractedText.trim() : "";
  let extractedText = localText;
  let scanStatus = hasLocalText ? "SCANNED_LOCAL" : "UPLOADED";

  if (!hasLocalText) {
    try {
      extractedText = await extractMedicalText(imageUrl);
      scanStatus = "SCANNED_OCR_SPACE";
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "";
      scanStatus = "SCAN_FAILED";
      extractedText = "No readable medical text was found in this image.";
      let message = "Image saved, but text extraction failed. Please try a clearer photo.";

      if (errorMessage.includes("OCR_SPACE_API_KEY")) {
        message = "Image saved. Add OCR_SPACE_API_KEY to .env to enable OCR.Space extraction.";
      } else if (
        errorMessage.includes("429") ||
        errorMessage.toLowerCase().includes("quota") ||
        errorMessage.toLowerCase().includes("rate_limit")
      ) {
        message =
          "Image saved. OCR.Space rejected the scan because the API key is rate-limited or has no available quota.";
      } else if (errorMessage.includes("401")) {
        message = "Image saved. OCR.Space rejected the scan because the API key is invalid.";
      }

      const record = await prisma.medicalRecord.create({
        data: {
          userId,
          title: fallbackTitle(body.fileName),
          fileName: body.fileName.trim(),
          imageUrl,
          extractedText,
          scanStatus,
        },
        select: {
          ...medicalRecordSelect,
        },
      });

      await saveMedicalAiAnalysis(record);

      return Response.json({ message, record }, { status: 201 });
    }
  }

  extractedText = summarizeMedicalText(extractedText, body.fileName);

  const existingSummaryRecord = await findExistingSummaryRecord(userId, extractedText, body.fileName);

  if (existingSummaryRecord) {
    return Response.json(
      {
        message: "This lab report summary is already saved, so Nora did not add another copy.",
        record: existingSummaryRecord,
        duplicate: true,
      },
      { status: 200 },
    );
  }

  const record = await prisma.medicalRecord.create({
    data: {
      userId,
      title: fallbackTitle(body.fileName),
      fileName: body.fileName.trim(),
      imageUrl,
      extractedText: extractedText || "No readable medical text was found in this image.",
      scanStatus,
    },
    select: {
      ...medicalRecordSelect,
    },
  });

  await saveMedicalAiAnalysis(record);

  return Response.json(
    {
      message:
        scanStatus === "SCANNED_LOCAL"
          ? "Report scanned locally and medical text saved."
          : "Report scanned with OCR.Space and medical text saved.",
      record,
    },
    { status: 201 },
  );
}

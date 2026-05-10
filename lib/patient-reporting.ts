import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";

import { classifyReportCategory, REPORT_CATEGORY_KEYWORDS, type ReportCategoryId, specialistForCategory } from "@/lib/patient-dashboard";
import { buildPatientFriendlySummary, classifyRiskFlags, buildMedicalDisclaimer } from "@/lib/patient-dashboard";
import { summarizeMedicalText } from "@/lib/medical-summarizer";

export type UploadResult = {
  diskPath: string;
  publicUrl: string;
  originalFileName: string;
  fileType: string;
  extension: string;
};

type OcrResult = {
  rawText: string;
  cleanedText: string;
  confidence: number | null;
};

const ALLOWED_EXTENSIONS = new Set([
  ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif",
  ".pdf", ".docx",
]);

const ALLOWED_CONTENT_TYPES = new Set([
  "image/jpeg", "image/jpg", "image/png", "image/webp",
  "image/heic", "image/heif",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);

function sanitizeSegment(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "") || "general";
}

function getUploadRoot() {
  return path.join(process.cwd(), "public", "uploads");
}

async function ensureDirectory(directory: string) {
  await fs.mkdir(directory, { recursive: true });
}

export function isAllowedReportFile(fileName: string, contentType: string) {
  const extension = path.extname(fileName).toLowerCase();
  return ALLOWED_EXTENSIONS.has(extension) || ALLOWED_CONTENT_TYPES.has(contentType);
}

export async function saveReportFile({
  file,
  patientId,
  category,
  requestOrigin,
}: {
  file: File;
  patientId: number;
  category: string;
  requestOrigin: string;
}): Promise<UploadResult> {
  const fileName = file.name || "report";
  if (!isAllowedReportFile(fileName, file.type)) {
    throw new Error("Only PDF, JPG, JPEG, PNG, WEBP, HEIC, and DOCX files are supported.");
  }

  const extension = path.extname(fileName).toLowerCase() || (file.type === "application/pdf" ? ".pdf" : ".png");
  const safeCategory = sanitizeSegment(category);
  const patientFolder = sanitizeSegment(String(patientId));
  const uploadRoot = getUploadRoot();
  const storageDir = path.join(uploadRoot, patientFolder, safeCategory);
  await ensureDirectory(storageDir);

  const storedName = `${crypto.randomUUID()}${extension}`;
  const diskPath = path.join(storageDir, storedName);
  const fileBuffer = Buffer.from(await file.arrayBuffer());
  await fs.writeFile(diskPath, fileBuffer);

  const publicPath = `/uploads/${patientFolder}/${safeCategory}/${storedName}`;
  return {
    diskPath,
    publicUrl: new URL(publicPath, requestOrigin).toString(),
    originalFileName: fileName,
    fileType: file.type || "application/octet-stream",
    extension,
  };
}

function cleanText(text: string): string {
  return text.replace(/\r/g, "\n").replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
}

// ── OCR.Space ────────────────────────────────────────────────────────────────

function getOcrApiKey() {
  return (
    process.env.OCR_SPACE_API_KEY?.trim() ||
    process.env.OPTIIC_API_KEY?.trim() ||
    ""
  );
}

async function ocrSpaceBuffer(
  buffer: Buffer,
  fileType: string,
  fileName: string,
): Promise<string> {
  const apiKey = getOcrApiKey();
  if (!apiKey) throw new Error("OCR_SPACE_API_KEY not configured.");

  const form = new FormData();
  form.set("apikey", apiKey);
  form.set("language", "eng");
  form.set("OCREngine", "2");
  form.set("scale", "true");
  form.set("detectOrientation", "true");
  form.set("isTable", "true");
  form.set("file", new Blob([new Uint8Array(buffer)], { type: fileType }), fileName);

  const res = await fetch("https://api.ocr.space/parse/image", {
    method: "POST",
    body: form,
    signal: AbortSignal.timeout(45_000),
  });

  const data = (await res.json()) as {
    ParsedResults?: Array<{ ParsedText?: string }>;
    IsErroredOnProcessing?: boolean;
    ErrorMessage?: string | string[];
  };

  if (data.IsErroredOnProcessing) {
    const msg = Array.isArray(data.ErrorMessage)
      ? data.ErrorMessage.join(" ")
      : (data.ErrorMessage ?? "OCR.Space error");
    throw new Error(msg);
  }

  return (data.ParsedResults ?? [])
    .map((r) => r.ParsedText?.trim() ?? "")
    .filter(Boolean)
    .join("\n\n");
}

// ── Tesseract fallback (local, for when OCR.Space unavailable) ───────────────

async function tesseractOcr(imageBuffer: Buffer): Promise<{ text: string; confidence: number | null }> {
  const { createWorker } = await import("tesseract.js");
  const worker = await createWorker("eng", 1, {
    langPath: process.cwd(),
    workerBlobURL: false,
  });
  try {
    const result = await worker.recognize(imageBuffer);
    return {
      text: result.data.text ?? "",
      confidence: typeof result.data.confidence === "number" ? result.data.confidence : null,
    };
  } finally {
    await worker.terminate().catch(() => null);
  }
}

async function preprocessImage(buffer: Buffer): Promise<Buffer> {
  const sharp = (await import("sharp")).default;
  return sharp(buffer)
    .grayscale()
    .normalize()
    .sharpen()
    .resize({ width: 2000, withoutEnlargement: true })
    .png()
    .toBuffer();
}

// ── PDF text extraction ──────────────────────────────────────────────────────

async function extractPdfText(buffer: Buffer): Promise<string> {
  const { PDFParse } = await import("pdf-parse");
  const parser = new PDFParse({ data: buffer });
  try {
    const result = await parser.getText();
    return result.text ?? "";
  } finally {
    await parser.destroy().catch(() => null);
  }
}

// ── Main entry point ─────────────────────────────────────────────────────────

export async function extractOcrFromBuffer({
  buffer,
  fileType,
  fileName = "report",
}: {
  buffer: Buffer;
  fileType: string;
  fileName?: string;
}): Promise<OcrResult> {
  // ── DOCX ──────────────────────────────────────────────────────────────────
  if (
    fileType === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
    fileType.includes("wordprocessingml")
  ) {
    const mammoth = await import("mammoth");
    const result = await mammoth.extractRawText({ buffer });
    const text = result.value ?? "";
    return { rawText: text.trim(), cleanedText: cleanText(text), confidence: 100 };
  }

  // ── PDF: try native text extraction first ──────────────────────────────────
  if (fileType === "application/pdf") {
    try {
      const pdfText = await extractPdfText(buffer);
      if (pdfText.trim().length > 80) {
        return { rawText: pdfText.trim(), cleanedText: cleanText(pdfText), confidence: 100 };
      }
    } catch {
      // Scanned PDF — fall through to OCR
    }
  }

  // ── HEIC/HEIF: convert to PNG first ───────────────────────────────────────
  let ocrBuffer = buffer;
  let ocrType = fileType;
  let ocrName = fileName;
  if (fileType === "image/heic" || fileType === "image/heif") {
    const sharp = (await import("sharp")).default;
    ocrBuffer = await sharp(buffer).png().toBuffer();
    ocrType = "image/png";
    ocrName = ocrName.replace(/\.(heic|heif)$/i, ".png");
  }

  // ── OCR.Space (primary) ───────────────────────────────────────────────────
  try {
    const text = await ocrSpaceBuffer(ocrBuffer, ocrType, ocrName);
    if (text.trim().length > 0) {
      return { rawText: text.trim(), cleanedText: cleanText(text), confidence: 90 };
    }
  } catch {
    // OCR.Space failed — try Tesseract
  }

  // ── Tesseract (fallback, images only) ─────────────────────────────────────
  if (ocrType.startsWith("image/")) {
    try {
      const preprocessed = await preprocessImage(ocrBuffer);
      const { text, confidence } = await tesseractOcr(preprocessed);
      if (text.trim().length > 0) {
        return { rawText: text.trim(), cleanedText: cleanText(text), confidence };
      }
    } catch {
      // Tesseract failed too — return empty, upload still proceeds
    }
  }

  return { rawText: "", cleanedText: "", confidence: null };
}

export function deriveReportCategory(text: string, fileName?: string | null): ReportCategoryId {
  return classifyReportCategory(text, fileName);
}

export function deriveStructuredSections(text: string) {
  const summary = summarizeMedicalText(text);
  return {
    overview: summary.summary,
    key_findings: summary.key_findings,
    risk_indicators: summary.risk_indicators,
    recommendations: summary.recommendations,
  };
}

export function buildSafeAnalysis({
  category,
  reportType,
  cleanedText,
}: {
  category: ReportCategoryId;
  reportType: string;
  cleanedText: string;
}) {
  const summary = summarizeMedicalText(cleanedText);
  const possibleRiskFlags = classifyRiskFlags(cleanedText);
  return {
    category,
    reportType,
    patientSummary: buildPatientFriendlySummary(category, cleanedText),
    doctorSummary: summary.summary || `Review this ${reportType.toLowerCase()} with the patient in context.`,
    abnormalFindings: summary.key_findings.slice(0, 5),
    possibleRiskFlags,
    recommendedSpecialist: specialistForCategory(category),
    urgencyLevel: possibleRiskFlags.length >= 3 ? "High" : possibleRiskFlags.length >= 1 ? "Medium" : "Low",
    disclaimer: buildMedicalDisclaimer(),
  };
}

export function keywordMatchesForCategory(text: string) {
  const lower = text.toLowerCase();
  return Object.entries(REPORT_CATEGORY_KEYWORDS).reduce<Record<string, string[]>>(
    (acc, [cat, keywords]) => {
      acc[cat] = keywords.filter((kw) => lower.includes(kw));
      return acc;
    },
    {},
  );
}

import { prisma } from "@/lib/prisma";
import { analyzeReportWithOpenAI } from "@/lib/patient-ai";
import { normalizeReportCategory, reportTypeForCategory } from "@/lib/patient-dashboard";
import { readReportFileBuffer } from "@/lib/patient-report-files";
import {
  deriveReportCategory,
  deriveStructuredSections,
  extractOcrFromBuffer,
  keywordMatchesForCategory,
} from "@/lib/patient-reporting";
import { resolvePatientSession } from "@/lib/patient-session";
import { getReportCategory, serializePatientReport } from "@/lib/patient-report-records";
import type { ReportCategoryId } from "@/lib/patient-dashboard";

export const runtime = "nodejs";
export const maxDuration = 300;

type RegenerateRouteContext = {
  params: Promise<{
    id: string;
  }>;
};

function parseReportId(value: string) {
  const reportId = Number(value);
  return Number.isInteger(reportId) && reportId > 0 ? reportId : null;
}

function asObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }

  return value as Record<string, unknown>;
}

function titleCaseCategory(category: ReportCategoryId) {
  return category.charAt(0).toUpperCase() + category.slice(1);
}

async function departmentForCategory(category: ReportCategoryId, reportType: string) {
  return prisma.medicalDepartment.upsert({
    where: { name: titleCaseCategory(category) },
    update: {
      description: reportType,
      icon: category,
    },
    create: {
      name: titleCaseCategory(category),
      icon: category,
      description: reportType,
    },
  });
}

export async function POST(request: Request, context: RegenerateRouteContext) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  const { id } = await context.params;
  const reportId = parseReportId(id);
  if (!reportId) {
    return Response.json({ message: "Invalid report ID." }, { status: 400 });
  }

  const report = await prisma.patientReport.findFirst({
    where: {
      id: reportId,
      patientId: session.user.id,
    },
    include: {
      department: true,
      patient: true,
    },
  });

  if (!report) {
    return Response.json({ message: "Report not found." }, { status: 404 });
  }

  let rawText = "";
  let cleanedText = "";
  let ocrConfidence: number | null = null;

  try {
    const buffer = await readReportFileBuffer(report.fileUrl);
    const ocr = await extractOcrFromBuffer({
      buffer,
      fileType: report.fileType,
      fileName: report.originalFileName,
    });
    rawText = ocr.rawText;
    cleanedText = ocr.cleanedText;
    ocrConfidence = ocr.confidence;
  } catch (error) {
    const updated = await prisma.patientReport.update({
      where: { id: report.id },
      data: {
        ocrStatus: "FAILED",
        llmSelfCheck: {
          ...asObject(report.llmSelfCheck),
          ocr_error: error instanceof Error ? error.message : "OCR regeneration failed.",
        },
      },
      include: {
        department: true,
        patient: true,
      },
    });

    return Response.json(serializePatientReport(updated));
  }

  const existingCategory = getReportCategory(report);
  const detectedCategory = normalizeReportCategory(
    cleanedText ? deriveReportCategory(cleanedText, report.originalFileName) : existingCategory,
  );
  const reportType = reportTypeForCategory(detectedCategory);
  const textForAnalysis = cleanedText || report.title || report.originalFileName;
  const structuredSections = deriveStructuredSections(textForAnalysis);
  const keywordHits = keywordMatchesForCategory(textForAnalysis);
  const detectedKeywords = keywordHits[detectedCategory] ?? [];
  const aiAnalysis = await analyzeReportWithOpenAI({
    category: detectedCategory,
    reportType,
    cleanedText: textForAnalysis,
    patientName: session.user.name,
    fileName: report.originalFileName,
  });
  const department = await departmentForCategory(detectedCategory, reportType);

  const updated = await prisma.patientReport.update({
    where: { id: report.id },
    data: {
      departmentId: department.id,
      extractedText: cleanedText || null,
      formattedText: cleanedText || null,
      structuredDataJson: {
        ...asObject(report.structuredDataJson),
        category: detectedCategory,
        department: detectedCategory,
        reportType,
        rawText,
        detectedKeywords,
        structuredSections,
        patientSummary: aiAnalysis.patientSummary,
        doctorSummary: aiAnalysis.doctorSummary,
        abnormalFindings: aiAnalysis.abnormalFindings,
        possibleRiskFlags: aiAnalysis.possibleRiskFlags,
        recommendedSpecialist: aiAnalysis.recommendedSpecialist,
        urgencyLevel: aiAnalysis.urgencyLevel,
        disclaimer: aiAnalysis.disclaimer,
      },
      summary: aiAnalysis.patientSummary,
      ruleWarnings: aiAnalysis.possibleRiskFlags.map((flag) => ({
        code: "RISK_FLAG",
        severity: "CAUTION",
        message: flag,
      })),
      validationStatus:
        aiAnalysis.urgencyLevel === "High"
          ? "HIGH_RISK"
          : aiAnalysis.urgencyLevel === "Medium"
            ? "CAUTION"
            : "SAFE",
      validationResults: {
        urgencyLevel: aiAnalysis.urgencyLevel,
        source: "ai",
      },
      clinicalSummaryJson: {
        patient_overview: aiAnalysis.patientSummary,
        key_findings: aiAnalysis.abnormalFindings,
        doctor_notes: [aiAnalysis.doctorSummary],
        risks_alerts: aiAnalysis.possibleRiskFlags,
        summary: aiAnalysis.patientSummary,
      },
      llmSelfCheck: {
        used_fallback: aiAnalysis.patientSummary.length > 0 && cleanedText.length === 0,
      },
      summarySource: "openai",
      ocrStatus: cleanedText ? "COMPLETED" : "NEEDS_REVIEW",
      ocrConfidence,
    },
    include: {
      department: true,
      patient: true,
    },
  });

  await prisma.medicalAiAnalysis.create({
    data: {
      userId: session.user.id,
      patientReportId: updated.id,
      source: "openai",
      extractedEntities: [],
      confidenceScore: ocrConfidence,
      ruleWarnings: aiAnalysis.possibleRiskFlags.map((flag) => ({
        code: "RISK_FLAG",
        severity: "CAUTION",
        message: flag,
      })),
      validationResults: {
        urgencyLevel: aiAnalysis.urgencyLevel,
      },
      doctorSummary: aiAnalysis.doctorSummary,
    },
  }).catch(() => null);

  return Response.json(serializePatientReport(updated));
}

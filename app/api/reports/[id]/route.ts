import { prisma } from "@/lib/prisma";
import { analyzeReportWithOpenAI } from "@/lib/patient-ai";
import { normalizeReportCategory, reportTypeForCategory } from "@/lib/patient-dashboard";
import { deleteLocalReportFile } from "@/lib/patient-report-files";
import { deriveStructuredSections, keywordMatchesForCategory } from "@/lib/patient-reporting";
import { resolvePatientSession } from "@/lib/patient-session";
import { getReportCategory, serializePatientReport } from "@/lib/patient-report-records";
import type { ReportCategoryId } from "@/lib/patient-dashboard";

export const runtime = "nodejs";
export const maxDuration = 300;

type ReportRouteContext = {
  params: Promise<{
    id: string;
  }>;
};

function parseReportId(value: string) {
  const reportId = Number(value);
  return Number.isInteger(reportId) && reportId > 0 ? reportId : null;
}

async function getOwnedReport(request: Request, context: ReportRouteContext) {
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

  return { report, session };
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

function asObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }

  return value as Record<string, unknown>;
}

async function buildAnalysisUpdate(args: {
  category: ReportCategoryId;
  cleanedText: string;
  patientName: string;
  fileName: string;
  existingStructuredData: unknown;
}) {
  const reportType = reportTypeForCategory(args.category);
  const textForAnalysis = args.cleanedText || args.fileName;
  const structuredSections = deriveStructuredSections(textForAnalysis);
  const keywordHits = keywordMatchesForCategory(textForAnalysis);
  const detectedKeywords = keywordHits[args.category] ?? [];
  const aiAnalysis = await analyzeReportWithOpenAI({
    category: args.category,
    reportType,
    cleanedText: textForAnalysis,
    patientName: args.patientName,
    fileName: args.fileName,
  });

  return {
    reportType,
    structuredSections,
    detectedKeywords,
    aiAnalysis,
    data: {
      structuredDataJson: {
        ...asObject(args.existingStructuredData),
        category: args.category,
        department: args.category,
        reportType,
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
        used_fallback: aiAnalysis.patientSummary.length > 0 && args.cleanedText.length === 0,
      },
      summarySource: "openai",
    },
  };
}

export async function GET(request: Request, context: ReportRouteContext) {
  const result = await getOwnedReport(request, context);
  if (result instanceof Response) {
    return result;
  }

  return Response.json(serializePatientReport(result.report));
}

export async function PATCH(request: Request, context: ReportRouteContext) {
  const result = await getOwnedReport(request, context);
  if (result instanceof Response) {
    return result;
  }

  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body) {
    return Response.json({ message: "Provide report updates." }, { status: 400 });
  }

  const existingCategory = getReportCategory(result.report);
  const nextCategory = normalizeReportCategory(
    typeof body.department === "string" ? body.department : existingCategory,
  );
  const nextTitle =
    typeof body.title === "string" && body.title.trim().length > 0
      ? body.title.trim()
      : result.report.title;
  const hasExtractedTextUpdate = typeof body.extracted_text === "string";
  const hasFormattedTextUpdate = typeof body.formatted_text === "string";
  const nextExtractedText = hasExtractedTextUpdate
    ? String(body.extracted_text).trim()
    : result.report.extractedText ?? "";
  const nextFormattedText =
    hasFormattedTextUpdate
      ? String(body.formatted_text).trim()
      : hasExtractedTextUpdate
        ? nextExtractedText
        : result.report.formattedText ?? nextExtractedText;
  const shouldReanalyze =
    hasExtractedTextUpdate ||
    hasFormattedTextUpdate ||
    typeof body.department === "string";

  const reportType = reportTypeForCategory(nextCategory);
  const department = await departmentForCategory(nextCategory, reportType);
  const analysisUpdate = shouldReanalyze
    ? await buildAnalysisUpdate({
        category: nextCategory,
        cleanedText: nextFormattedText || nextExtractedText,
        patientName: result.session.user.name,
        fileName: result.report.originalFileName,
        existingStructuredData: result.report.structuredDataJson,
      })
    : null;

  const updated = await prisma.patientReport.update({
    where: { id: result.report.id },
    data: {
      title: nextTitle,
      departmentId: department.id,
      extractedText: nextExtractedText || null,
      formattedText: nextFormattedText || null,
      ocrStatus: nextExtractedText || nextFormattedText ? "COMPLETED" : result.report.ocrStatus,
      ...(analysisUpdate?.data ?? {}),
    },
    include: {
      department: true,
      patient: true,
    },
  });

  if (analysisUpdate) {
    await prisma.medicalAiAnalysis.create({
      data: {
        userId: result.session.user.id,
        patientReportId: updated.id,
        source: "openai",
        extractedEntities: [],
        confidenceScore: updated.ocrConfidence,
        ruleWarnings: analysisUpdate.data.ruleWarnings,
        validationResults: analysisUpdate.data.validationResults,
        doctorSummary: analysisUpdate.aiAnalysis.doctorSummary,
      },
    }).catch(() => null);
  }

  return Response.json(serializePatientReport(updated));
}

export async function DELETE(request: Request, context: ReportRouteContext) {
  const result = await getOwnedReport(request, context);
  if (result instanceof Response) {
    return result;
  }

  await deleteLocalReportFile(result.report.fileUrl);
  await prisma.patientReport.delete({
    where: { id: result.report.id },
  });

  return Response.json({ message: "Report deleted." });
}

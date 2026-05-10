import fs from "node:fs/promises";

import { prisma } from "@/lib/prisma";
import { resolvePatientSession } from "@/lib/patient-session";
import { analyzeReportWithOpenAI } from "@/lib/patient-ai";
import { deriveReportCategory, deriveStructuredSections, extractOcrFromBuffer, keywordMatchesForCategory, saveReportFile } from "@/lib/patient-reporting";
import { normalizeReportCategory, reportTypeForCategory } from "@/lib/patient-dashboard";
import { serializePatientReport } from "@/lib/patient-report-records";

export const runtime = "nodejs";
export const maxDuration = 300;

export async function POST(request: Request) {
  const session = await resolvePatientSession(request);
  if (session instanceof Response) {
    return session;
  }

  try {
    const formData = await request.formData().catch(() => null);
    const file = formData?.get("file");

    if (!(file instanceof File)) {
      return Response.json({ message: "A report file is required." }, { status: 400 });
    }

    const origin = new URL(request.url).origin;
    const categoryFromForm = typeof formData?.get("category") === "string" ? String(formData.get("category")) : "";
    const manualCategory = normalizeReportCategory(categoryFromForm);
    const titleFromForm = typeof formData?.get("title") === "string" ? String(formData.get("title")).trim() : "";
    const notesFromForm = typeof formData?.get("notes") === "string" ? String(formData.get("notes")).trim() : "";

    const upload = await saveReportFile({
      file,
      patientId: session.user.id,
      category: manualCategory,
      requestOrigin: origin,
    });

    const buffer = Buffer.from(await file.arrayBuffer());
    let ocrText = "";
    let rawText = "";
    let ocrConfidence: number | null = null;
    try {
      const ocr = await extractOcrFromBuffer({
        buffer,
        fileType: file.type || upload.fileType,
        fileName: file.name,
      });
      rawText = ocr.rawText;
      ocrText = ocr.cleanedText;
      ocrConfidence = ocr.confidence;
    } catch (error) {
      ocrText = "";
      rawText = error instanceof Error ? error.message : "";
    }

    const detectedCategory = manualCategory !== "general" ? manualCategory : deriveReportCategory(ocrText || titleFromForm || file.name, file.name);
    const reportType = reportTypeForCategory(detectedCategory);
    const structuredSections = deriveStructuredSections(ocrText || titleFromForm || file.name);
    const keywordHits = keywordMatchesForCategory(ocrText || titleFromForm || file.name);
    const detectedKeywords = keywordHits[detectedCategory] ?? [];
    const aiAnalysis = await analyzeReportWithOpenAI({
      category: detectedCategory,
      reportType,
      cleanedText: ocrText || titleFromForm || file.name,
      patientName: session.user.name,
      fileName: file.name,
    });

    if (!aiAnalysis.isMedical && ocrText.length >= 50) {
      await fs.unlink(upload.diskPath).catch(() => null);
      return Response.json(
        {
          message:
            "This file does not appear to be a medical document. Please upload a lab report, prescription, scan, clinical note, or other health record.",
        },
        { status: 422 },
      );
    }

    const department = await prisma.medicalDepartment.upsert({
      where: { name: detectedCategory.charAt(0).toUpperCase() + detectedCategory.slice(1) },
      update: {},
      create: {
        name: detectedCategory.charAt(0).toUpperCase() + detectedCategory.slice(1),
        icon: detectedCategory,
        description: reportType,
      },
    });

    const report = await prisma.patientReport.create({
      data: {
        patientId: session.user.id,
        departmentId: department.id,
        title: titleFromForm || file.name.replace(/\.[^.]+$/, ""),
        originalFileName: file.name,
        fileUrl: upload.publicUrl,
        fileType: file.type || upload.fileType,
        extractedText: ocrText || null,
        formattedText: ocrText || null,
        structuredDataJson: {
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
          notes: notesFromForm,
        },
        summary: aiAnalysis.patientSummary,
        extractedEntities: [],
        ruleWarnings: aiAnalysis.possibleRiskFlags.map((flag) => ({ code: "RISK_FLAG", severity: "CAUTION", message: flag })),
        validationStatus: aiAnalysis.urgencyLevel === "High" ? "HIGH_RISK" : aiAnalysis.urgencyLevel === "Medium" ? "CAUTION" : "SAFE",
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
          used_fallback: aiAnalysis.patientSummary.length > 0 && ocrText.length === 0,
        },
        summarySource: "openai",
        ocrStatus: ocrText ? "COMPLETED" : "NEEDS_REVIEW",
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
        patientReportId: report.id,
        source: "openai",
        extractedEntities: [],
        confidenceScore: ocrConfidence,
        ruleWarnings: aiAnalysis.possibleRiskFlags.map((flag) => ({ code: "RISK_FLAG", severity: "CAUTION", message: flag })),
        validationResults: {
          urgencyLevel: aiAnalysis.urgencyLevel,
        },
        doctorSummary: aiAnalysis.doctorSummary,
      },
    }).catch(() => null);

    return Response.json(
      serializePatientReport(report),
      { status: 201 },
    );
  } catch (error) {
    return Response.json(
      { message: error instanceof Error ? error.message : "Report upload failed." },
      { status: error instanceof Error && error.message.includes("supported") ? 400 : 500 },
    );
  }
}

import { analyzeReportWithOpenAI } from "@/lib/patient-ai";
import { deriveReportCategory } from "@/lib/patient-reporting";
import { normalizeReportCategory, reportTypeForCategory } from "@/lib/patient-dashboard";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null;
  if (!body || typeof body.text !== "string") {
    return Response.json({ message: "Report text is required." }, { status: 400 });
  }

  const cleanedText = body.text.trim();
  if (!cleanedText) {
    return Response.json({ message: "OCR text cannot be empty." }, { status: 400 });
  }

  const category = deriveReportCategory(cleanedText, typeof body.fileName === "string" ? body.fileName : "");
  const requestedCategory = normalizeReportCategory(typeof body.category === "string" ? body.category : category);
  const reportType = typeof body.reportType === "string" && body.reportType.trim()
    ? body.reportType.trim()
    : reportTypeForCategory(requestedCategory);

  const analysis = await analyzeReportWithOpenAI({
    category: requestedCategory,
    reportType,
    cleanedText,
    patientName: "Patient",
    fileName: typeof body.fileName === "string" ? body.fileName : undefined,
  });

  return Response.json(analysis);
}

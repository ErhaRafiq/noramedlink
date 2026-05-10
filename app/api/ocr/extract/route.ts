import { extractOcrFromBuffer, deriveReportCategory, deriveStructuredSections } from "@/lib/patient-reporting";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const formData = await request.formData().catch(() => null);
  const file = formData?.get("file");

  if (!(file instanceof File)) {
    return Response.json({ message: "A report file is required." }, { status: 400 });
  }

  try {
    const buffer = Buffer.from(await file.arrayBuffer());
    const ocr = await extractOcrFromBuffer({
      buffer,
      fileType: file.type || "application/octet-stream",
    });
    const category = deriveReportCategory(ocr.cleanedText || file.name, file.name);
    const sections = deriveStructuredSections(ocr.cleanedText || file.name);

    return Response.json({
      rawText: ocr.rawText,
      cleanedText: ocr.cleanedText,
      possibleReportType: category === "general" ? "General medical report" : `${category} report`,
      detectedKeywords: [],
      structuredSections: sections,
    });
  } catch (error) {
    return Response.json(
      { message: error instanceof Error ? error.message : "OCR extraction failed." },
      { status: 400 },
    );
  }
}

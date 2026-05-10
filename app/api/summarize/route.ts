import { summarizeMedicalText } from "@/lib/medical-summarizer";
import { prisma } from "@/lib/prisma";

export const runtime = "nodejs";

type SummarizeBody = {
  userId?: unknown;
  text?: unknown;
};

type BackendSummary = {
  summary?: unknown;
  warning?: unknown;
  detail?: unknown;
  message?: unknown;
};

function isSummarizeBody(value: unknown): value is SummarizeBody {
  return Boolean(value && typeof value === "object");
}

function parseUserId(value: unknown) {
  const userId = Number(value);

  return Number.isInteger(userId) && userId > 0 ? userId : null;
}

function isUsableExtractedText(value: string | null) {
  return Boolean(
    value?.trim() &&
      !value.includes(
        "AI scanning is not configured yet. Add a backend OCR provider to enable automatic text extraction.",
      ),
  );
}

function backendBaseUrl() {
  return (
    process.env.SERVER_API_URL ||
    process.env.FASTAPI_URL ||
    "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
}

function formatBackendDetail(data: BackendSummary) {
  if (typeof data.detail === "string") {
    return data.detail;
  }
  if (typeof data.message === "string") {
    return data.message;
  }
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return JSON.stringify(item);
      })
      .join(" ");
  }
  return "Unable to generate OpenAI clinical summary.";
}

async function summarizeWithBackend(text: string) {
  let response: Response;

  try {
    response = await fetch(`${backendBaseUrl()}/nlp/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, category: "medical-report" }),
      cache: "no-store",
    });
  } catch {
    throw new Error("FastAPI summarization service is not reachable.");
  }

  const data = (await response.json().catch(() => ({}))) as BackendSummary;

  if (!response.ok) {
    throw new Error(formatBackendDetail(data));
  }

  if (typeof data.summary !== "string" || !data.summary.trim()) {
    throw new Error("FastAPI returned an invalid summary response.");
  }

  return {
    summary: data.summary.trim(),
    warning: typeof data.warning === "string" ? data.warning : null,
  };
}

async function getSavedReportText(userId: number) {
  const records = await prisma.patientReport.findMany({
    where: { patientId: userId },
    orderBy: { uploadDate: "desc" },
    select: {
      title: true,
      originalFileName: true,
      extractedText: true,
      formattedText: true,
      uploadDate: true,
    },
  });

  return records
    .filter((record) => isUsableExtractedText(record.formattedText || record.extractedText))
    .map((record) =>
      [
        `Report: ${record.title}`,
        `File: ${record.originalFileName}`,
        `Uploaded: ${record.uploadDate.toISOString()}`,
        (record.formattedText || record.extractedText)?.trim(),
      ].join("\n"),
    )
    .join("\n\n");
}

export async function POST(request: Request) {
  let body: unknown;

  try {
    body = await request.json();
  } catch {
    return Response.json(
      { message: "Request body must be valid JSON." },
      { status: 400 },
    );
  }

  if (!isSummarizeBody(body) || typeof body.text !== "string") {
    const userId = isSummarizeBody(body) ? parseUserId(body.userId) : null;

    if (!userId) {
      return Response.json(
        { message: "Provide report text or a valid userId for saved reports." },
        { status: 400 },
      );
    }

    const savedReportText = await getSavedReportText(userId);

    if (savedReportText.length < 20) {
      return Response.json(
        { message: "No readable saved report text found for this patient yet." },
        { status: 404 },
      );
    }

    try {
      const backendSummary = await summarizeWithBackend(savedReportText);
      return Response.json({
        ...summarizeMedicalText(savedReportText),
        ...backendSummary,
      });
    } catch (error) {
      return Response.json(
        {
          message: error instanceof Error ? error.message : "Unable to summarize saved reports.",
        },
        { status: 502 },
      );
    }
  }

  const text = body.text.trim();

  if (text.length < 20) {
    return Response.json(
      { message: "Enter at least 20 characters of medical report text." },
      { status: 400 },
    );
  }

  if (text.length > 20000) {
    return Response.json(
      { message: "Medical report text must be 20,000 characters or less." },
      { status: 413 },
    );
  }

  try {
    const backendSummary = await summarizeWithBackend(text);
    return Response.json({
      ...summarizeMedicalText(text),
      ...backendSummary,
    });
  } catch (error) {
    return Response.json(
      {
        message: error instanceof Error ? error.message : "Unable to summarize this report.",
      },
      { status: 502 },
    );
  }
}

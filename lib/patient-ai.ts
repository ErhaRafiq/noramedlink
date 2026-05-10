import { buildSafeAnalysis } from "@/lib/patient-reporting";
import type { ReportCategoryId } from "@/lib/patient-dashboard";
import { buildMedicalDisclaimer } from "@/lib/patient-dashboard";

const OPENAI_BASE_URL = "https://api.openai.com/v1/chat/completions";

type OpenAIJsonRequest = {
  system: string;
  user: string;
  model?: string;
  temperature?: number;
};

function getOpenAIApiKey() {
  return process.env.OPENAI_API_KEY?.trim() || "";
}

function getModel(defaultModel: string) {
  return process.env.OPENAI_SCAN_MODEL?.trim() || process.env.OPENAI_CHAT_MODEL?.trim() || defaultModel;
}

async function parseJsonFromAssistant(content: string) {
  const trimmed = content.trim();
  const jsonText = trimmed.startsWith("```") ? trimmed.replace(/^```(?:json)?/i, "").replace(/```$/i, "").trim() : trimmed;
  return JSON.parse(jsonText) as Record<string, unknown>;
}

async function callOpenAIJson({ system, user, model, temperature = 0.2 }: OpenAIJsonRequest) {
  const apiKey = getOpenAIApiKey();
  if (!apiKey) {
    throw new Error("OPENAI_API_KEY is not configured.");
  }

  const response = await fetch(OPENAI_BASE_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: model ?? getModel("gpt-4.1-mini"),
      temperature,
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: system },
        { role: "user", content: user },
      ],
    }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "OpenAI request failed.");
  }

  const data = (await response.json()) as {
    choices?: Array<{ message?: { content?: string | null } }>;
  };

  const content = data.choices?.[0]?.message?.content ?? "";
  if (!content.trim()) {
    throw new Error("OpenAI returned an empty response.");
  }

  return parseJsonFromAssistant(content);
}

export async function analyzeReportWithOpenAI(args: {
  category: ReportCategoryId;
  reportType: string;
  cleanedText: string;
  patientName: string;
  fileName?: string;
}) {
  const prompt = `
Return only JSON with these fields:
isMedical, category, reportType, patientSummary, doctorSummary, abnormalFindings, possibleRiskFlags, recommendedSpecialist, urgencyLevel, disclaimer.

Rules:
- isMedical: true if the document is a medical or health record (lab report, blood test, prescription, X-ray, MRI, ECG, clinical note, vaccine record, discharge summary, etc). false if it is a selfie, food photo, landscape, receipt, ID card, invoice, or any other non-health document.
- Use safe wording. Never provide a diagnosis.
- Use "Possible risk detected" style language.
- Disclaimer must be: "${buildMedicalDisclaimer()}"
- Keep patientSummary short and friendly.
- Keep doctorSummary concise and clinically useful.
- abnormalFindings and possibleRiskFlags must be arrays of strings.
- urgencyLevel must be Low, Medium, or High.
- If isMedical is false, set patientSummary and doctorSummary to empty strings and all arrays to [].

Patient name: ${args.patientName}
File name: ${args.fileName ?? "unknown"}
Category: ${args.category}
Report type: ${args.reportType}
OCR text:
${args.cleanedText.slice(0, 12000)}
`.trim();

  try {
    const result = await callOpenAIJson({
      system:
        "You are a medical report assistant for a healthcare SaaS. You must be safe, cautious, and never claim a diagnosis.",
      user: prompt,
      temperature: 0.15,
    });

    return {
      isMedical: result.isMedical !== false,
      category: String(result.category ?? args.category),
      reportType: String(result.reportType ?? args.reportType),
      patientSummary: String(result.patientSummary ?? ""),
      doctorSummary: String(result.doctorSummary ?? ""),
      abnormalFindings: Array.isArray(result.abnormalFindings) ? result.abnormalFindings.map(String).slice(0, 8) : [],
      possibleRiskFlags: Array.isArray(result.possibleRiskFlags) ? result.possibleRiskFlags.map(String).slice(0, 8) : [],
      recommendedSpecialist: String(result.recommendedSpecialist ?? "General Physician"),
      urgencyLevel: String(result.urgencyLevel ?? "Low"),
      disclaimer: buildMedicalDisclaimer(),
    };
  } catch {
    return {
      isMedical: true,
      ...buildSafeAnalysis({
        category: args.category,
        reportType: args.reportType,
        cleanedText: args.cleanedText,
      }),
    };
  }
}

export async function answerPatientAssistant(args: {
  message: string;
  context: string;
  patientName: string;
}) {
  const prompt = `
Patient name: ${args.patientName}
Context:
${args.context.slice(0, 12000)}

Question:
${args.message}

Reply with JSON keys: answer, disclaimer.
Rules:
- Use safe medical wording.
- Never provide a diagnosis.
- The answer should be practical and short.
- Disclaimer must be: "${buildMedicalDisclaimer()}"
`.trim();

  try {
    const result = await callOpenAIJson({
      system:
        "You are Nora, a patient-facing medical assistant. Be careful, concise, and do not diagnose.",
      user: prompt,
      temperature: 0.2,
    });

    return {
      answer: String(result.answer ?? result.message ?? result.response ?? ""),
      disclaimer: buildMedicalDisclaimer(),
    };
  } catch {
    return {
      answer:
        "I can help you summarize reports, but I need the patient data service configured before I can answer live questions.",
      disclaimer: buildMedicalDisclaimer(),
    };
  }
}


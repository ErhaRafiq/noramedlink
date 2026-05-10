export type MedicalSummaryResult = {
  summary: string;
  key_findings: string[];
  risk_indicators: string[];
  recommendations: string[];
};

type ExtractedEntity = {
  label: string;
  text: string;
  negated: boolean;
};

type MeasurementRule = {
  name: string;
  pattern: RegExp;
  low?: number;
  high?: number;
  unit?: string;
};

const medicalTerms = [
  "fever",
  "cough",
  "pain",
  "chest pain",
  "shortness of breath",
  "breathlessness",
  "vomiting",
  "nausea",
  "diarrhea",
  "infection",
  "pneumonia",
  "asthma",
  "diabetes",
  "hypertension",
  "anemia",
  "anaemia",
  "jaundice",
  "hepatitis",
  "kidney",
  "renal",
  "liver",
  "cardiac",
  "heart",
  "stroke",
  "seizure",
  "pregnancy",
  "allergy",
  "edema",
  "swelling",
  "bleeding",
  "dizziness",
  "fatigue",
];

const urgentTerms = [
  "critical",
  "severe",
  "emergency",
  "acute",
  "positive",
  "high",
  "low",
  "abnormal",
  "elevated",
  "reduced",
  "infection",
  "failure",
  "stroke",
  "bleeding",
  "chest pain",
  "shortness of breath",
];

const negationWords = [
  "no",
  "not",
  "without",
  "denies",
  "denied",
  "negative for",
  "absence of",
  "free of",
];

const stopWords = new Set([
  "a",
  "an",
  "and",
  "are",
  "as",
  "at",
  "be",
  "by",
  "for",
  "from",
  "has",
  "have",
  "in",
  "is",
  "it",
  "of",
  "on",
  "or",
  "patient",
  "report",
  "the",
  "this",
  "to",
  "was",
  "were",
  "with",
]);

const measurementRules: MeasurementRule[] = [
  { name: "Hemoglobin", pattern: /\b(?:hb|hemoglobin|haemoglobin)\s*[:=-]?\s*(\d+(?:\.\d+)?)/gi, low: 12, high: 17.5, unit: "g/dL" },
  { name: "WBC", pattern: /\b(?:wbc|white blood cells?)\s*[:=-]?\s*(\d+(?:\.\d+)?)/gi, low: 4, high: 11, unit: "x10^9/L" },
  { name: "Platelets", pattern: /\b(?:platelet|platelets)\s*[:=-]?\s*(\d+(?:\.\d+)?)/gi, low: 150, high: 450, unit: "x10^9/L" },
  { name: "Glucose", pattern: /\b(?:glucose|sugar|blood sugar|fbs|rbs)\s*[:=-]?\s*(\d+(?:\.\d+)?)/gi, low: 70, high: 180, unit: "mg/dL" },
  { name: "HbA1c", pattern: /\b(?:hba1c|a1c)\s*[:=-]?\s*(\d+(?:\.\d+)?)/gi, high: 6.5, unit: "%" },
  { name: "Creatinine", pattern: /\b(?:creatinine)\s*[:=-]?\s*(\d+(?:\.\d+)?)/gi, high: 1.3, unit: "mg/dL" },
  { name: "Urea", pattern: /\b(?:urea)\s*[:=-]?\s*(\d+(?:\.\d+)?)/gi, high: 45, unit: "mg/dL" },
  { name: "Bilirubin", pattern: /\b(?:bilirubin)\s*[:=-]?\s*(\d+(?:\.\d+)?)/gi, high: 1.2, unit: "mg/dL" },
  { name: "ALT", pattern: /\b(?:alt|sgpt)\s*[:=-]?\s*(\d+(?:\.\d+)?)/gi, high: 56, unit: "U/L" },
  { name: "AST", pattern: /\b(?:ast|sgot)\s*[:=-]?\s*(\d+(?:\.\d+)?)/gi, high: 40, unit: "U/L" },
  { name: "LDL", pattern: /\b(?:ldl)\s*[:=-]?\s*(\d+(?:\.\d+)?)/gi, high: 130, unit: "mg/dL" },
  { name: "HDL", pattern: /\b(?:hdl)\s*[:=-]?\s*(\d+(?:\.\d+)?)/gi, low: 40, unit: "mg/dL" },
  { name: "Triglycerides", pattern: /\b(?:triglycerides?|tg)\s*[:=-]?\s*(\d+(?:\.\d+)?)/gi, high: 150, unit: "mg/dL" },
  { name: "SpO2", pattern: /\b(?:spo2|oxygen saturation)\s*[:=-]?\s*(\d+(?:\.\d+)?)/gi, low: 95, unit: "%" },
];

function cleanText(text: string) {
  return text
    .replace(/\r/g, "\n")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function splitSentences(text: string) {
  return cleanText(text)
    .split(/(?<=[.!?])\s+|\n+/)
    .map((sentence) => sentence.trim())
    .filter((sentence) => sentence.length > 0);
}

function tokenize(text: string) {
  return text
    .toLowerCase()
    .match(/[a-z][a-z-]+|\d+(?:\.\d+)?/g)
    ?.filter((token) => !stopWords.has(token)) ?? [];
}

function unique(values: string[]) {
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function isNegated(sentence: string, term: string) {
  const normalized = sentence.toLowerCase();
  const termIndex = normalized.indexOf(term.toLowerCase());

  if (termIndex < 0) {
    return false;
  }

  const beforeTerm = normalized.slice(Math.max(0, termIndex - 36), termIndex);

  return negationWords.some((word) => beforeTerm.includes(word));
}

function extractEntities(sentences: string[]) {
  const entities: ExtractedEntity[] = [];

  for (const sentence of sentences) {
    for (const term of medicalTerms) {
      const matcher = new RegExp(`\\b${escapeRegExp(term)}\\b`, "i");

      if (matcher.test(sentence)) {
        entities.push({
          label: term,
          text: sentence,
          negated: isNegated(sentence, term),
        });
      }
    }
  }

  return entities;
}

function getAbnormalMeasurements(text: string) {
  const findings: string[] = [];

  for (const rule of measurementRules) {
    const matches = Array.from(text.matchAll(rule.pattern));

    for (const match of matches) {
      const rawValue = match[1];
      const value = Number(rawValue);
      const exactText = match[0].replace(/\s+/g, " ").trim();
      const isLow = typeof rule.low === "number" && value < rule.low;
      const isHigh = typeof rule.high === "number" && value > rule.high;

      if (isLow || isHigh) {
        const direction = isLow ? "low" : "high";
        findings.push(`${rule.name} ${rawValue}${rule.unit ? ` ${rule.unit}` : ""} is ${direction} (${exactText})`);
      }
    }
  }

  const bpMatches = Array.from(text.matchAll(/\b(?:bp|blood pressure)\s*[:=-]?\s*(\d{2,3})\s*\/\s*(\d{2,3})\b/gi));

  for (const match of bpMatches) {
    const systolic = Number(match[1]);
    const diastolic = Number(match[2]);

    if (systolic >= 140 || diastolic >= 90) {
      findings.push(`Blood pressure ${match[1]}/${match[2]} is high`);
    }
  }

  return unique(findings).slice(0, 8);
}

function scoreSentences(sentences: string[]) {
  const tokenizedSentences = sentences.map(tokenize);
  const documentFrequency = new Map<string, number>();

  for (const tokens of tokenizedSentences) {
    for (const token of new Set(tokens)) {
      documentFrequency.set(token, (documentFrequency.get(token) ?? 0) + 1);
    }
  }

  return sentences.map((sentence, index) => {
    const tokens = tokenizedSentences[index];
    const termFrequency = new Map<string, number>();

    for (const token of tokens) {
      termFrequency.set(token, (termFrequency.get(token) ?? 0) + 1);
    }

    let score = 0;

    for (const [token, count] of termFrequency) {
      const idf = Math.log((sentences.length + 1) / ((documentFrequency.get(token) ?? 0) + 1)) + 1;
      score += count * idf;
    }

    const lowerSentence = sentence.toLowerCase();
    const medicalBoost = medicalTerms.some((term) => lowerSentence.includes(term)) ? 2 : 0;
    const urgentBoost = urgentTerms.some((term) => lowerSentence.includes(term)) ? 2.5 : 0;
    const numberBoost = /\d/.test(sentence) ? 1.5 : 0;

    return {
      index,
      sentence,
      score: score / Math.max(tokens.length, 1) + medicalBoost + urgentBoost + numberBoost,
    };
  });
}

function buildExtractiveSummary(sentences: string[]) {
  if (sentences.length <= 2) {
    return sentences.join(" ");
  }

  const selected = scoreSentences(sentences)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)
    .sort((a, b) => a.index - b.index)
    .map((item) => item.sentence);

  return selected.join(" ");
}

function buildKeyFindings(entities: ExtractedEntity[], abnormalValues: string[]) {
  const positiveEntities = entities
    .filter((entity) => !entity.negated)
    .map((entity) => entity.text);
  const negatedEntities = entities
    .filter((entity) => entity.negated)
    .map((entity) => `Negated finding: ${entity.text}`);

  return unique([...abnormalValues, ...positiveEntities, ...negatedEntities]).slice(0, 8);
}

function buildRiskIndicators(entities: ExtractedEntity[], abnormalValues: string[], sentences: string[]) {
  const entityRisks = entities
    .filter((entity) => !entity.negated && urgentTerms.some((term) => entity.text.toLowerCase().includes(term)))
    .map((entity) => entity.text);
  const sentenceRisks = sentences.filter((sentence) => {
    const normalized = sentence.toLowerCase();
    return urgentTerms.some(
      (term) => normalized.includes(term) && !isNegated(sentence, term),
    );
  });

  return unique([...abnormalValues, ...entityRisks, ...sentenceRisks]).slice(0, 8);
}

function buildRecommendations(riskIndicators: string[], abnormalValues: string[], hasContent: boolean) {
  if (!hasContent) {
    return ["Enter report text to generate a structured summary."];
  }

  const recommendations = [
    "Review this summary with a qualified clinician before making care decisions.",
    "Compare flagged values with the lab reference ranges printed on the original report.",
  ];

  if (abnormalValues.length > 0) {
    recommendations.push("Follow up with a doctor for the abnormal values listed above.");
  }

  if (riskIndicators.length > 0) {
    recommendations.push("Seek prompt medical advice if symptoms are severe, worsening, or associated with chest pain, breathing difficulty, confusion, or bleeding.");
  }

  return recommendations.slice(0, 4);
}

export function summarizeMedicalText(input: string): MedicalSummaryResult {
  const text = cleanText(input);
  const sentences = splitSentences(text);
  const entities = extractEntities(sentences);
  const abnormalValues = getAbnormalMeasurements(text);
  const keyFindings = buildKeyFindings(entities, abnormalValues);
  const riskIndicators = buildRiskIndicators(entities, abnormalValues, sentences);

  return {
    summary: sentences.length > 0 ? buildExtractiveSummary(sentences) : "",
    key_findings: keyFindings,
    risk_indicators: riskIndicators,
    recommendations: buildRecommendations(riskIndicators, abnormalValues, sentences.length > 0),
  };
}

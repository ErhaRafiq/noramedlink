export const runtime = "nodejs";

const OPEN_FDA_LABEL_ENDPOINT = "https://api.fda.gov/drug/label.json";

function normalizeText(value) {
  return value.trim().toLowerCase();
}

function asTextArray(value) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item) => typeof item === "string" && item.trim().length > 0);
}

function buildOpenFdaUrl(drugName) {
  const url = new URL(OPEN_FDA_LABEL_ENDPOINT);

  // Search OpenFDA labels by generic name and keep the response small for frontend use.
  url.searchParams.set("search", `openfda.generic_name:"${drugName}"`);
  url.searchParams.set("limit", "1");

  return url;
}

async function fetchDrugLabel(drugName) {
  const response = await fetch(buildOpenFdaUrl(drugName), {
    headers: {
      Accept: "application/json",
    },
    next: {
      revalidate: 60 * 60,
    },
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new Error(`OpenFDA request failed with status ${response.status}.`);
  }

  const data = await response.json();
  const label = Array.isArray(data.results) ? data.results[0] : null;

  if (!label) {
    return null;
  }

  // Extract only the drug label sections needed by the risk checker.
  return {
    warnings: asTextArray(label.warnings),
    contraindications: asTextArray(label.contraindications),
    adverseReactions: asTextArray(label.adverse_reactions),
  };
}

function detectRisk({ allergy, contraindications, warnings }) {
  const reasons = [];
  const normalizedAllergy = allergy ? normalizeText(allergy) : "";
  const contraindicationText = contraindications.join(" ").toLowerCase();

  // Allergy match is treated as the strongest signal because it may indicate immediate harm.
  if (normalizedAllergy && contraindicationText.includes(normalizedAllergy)) {
    reasons.push("Allergy matches the drug contraindications.");
    return { risk: "CRITICAL RISK", reasons };
  }

  // Contraindications indicate the drug should not be used in specific conditions.
  if (contraindications.length > 0) {
    reasons.push("Contraindications were found for this drug.");
    return { risk: "HIGH RISK", reasons };
  }

  // Warnings indicate the drug needs caution or medical supervision.
  if (warnings.length > 0) {
    reasons.push("Warnings were found for this drug.");
    return { risk: "MEDIUM RISK", reasons };
  }

  reasons.push("No warnings or contraindications were found in the OpenFDA label.");
  return { risk: "SAFE", reasons };
}

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const drugA = searchParams.get("drugA")?.trim() ?? "";
  const drugB = searchParams.get("drugB")?.trim() ?? "";
  const allergy = searchParams.get("allergy")?.trim() ?? "";

  if (!drugA) {
    return Response.json(
      { message: "Query parameter drugA is required." },
      { status: 400 },
    );
  }

  try {
    const drugALabel = await fetchDrugLabel(drugA);

    if (!drugALabel) {
      return Response.json(
        { message: `No OpenFDA label found for ${drugA}.` },
        { status: 404 },
      );
    }

    const drugBLabel = drugB ? await fetchDrugLabel(drugB) : null;

    if (drugB && !drugBLabel) {
      return Response.json(
        { message: `No OpenFDA label found for ${drugB}.` },
        { status: 404 },
      );
    }

    const warnings = [
      ...drugALabel.warnings,
      ...(drugBLabel?.warnings ?? []),
    ];
    const contraindications = [
      ...drugALabel.contraindications,
      ...(drugBLabel?.contraindications ?? []),
    ];
    const adverseReactions = [
      ...drugALabel.adverseReactions,
      ...(drugBLabel?.adverseReactions ?? []),
    ];

    const { risk, reasons } = detectRisk({
      allergy,
      contraindications,
      warnings,
    });

    return Response.json({
      drugA,
      drugB,
      risk,
      reasons,
      warnings,
      contraindications,
      adverse_reactions: adverseReactions,
    });
  } catch (error) {
    console.error("Drug check API error:", error);

    return Response.json(
      { message: "Unable to check drug safety right now." },
      { status: 502 },
    );
  }
}

/**
 * PMDC registration numbers. Mirrors backend/services/pmdc.py (normalize_registration), which checks again.
 *
 * The PMDC register searches an exact number in the form `digits-ending`, for example `12345-P` or `1815-AJK`.
 * The endings the register has numbers under were found by asking it: P, N, S, B, D, F and AJK. "12345P",
 * "12345/P" and "12345" find nothing there, so a number is written in that form before it is saved.
 */
export const PMDC_SUFFIXES = ["AJK", "B", "D", "F", "N", "P", "S"] as const;
export const PMDC_EXAMPLE = "12345-P";
export const PMDC_FORMAT_HELP = `Enter the number as printed on your PMDC certificate: digits, a dash and the ending (${PMDC_SUFFIXES.join(", ")}), for example ${PMDC_EXAMPLE} or 1815-AJK.`;
/** The PMDC page where anyone can look a doctor up by registration number. */
export const PMDC_REGISTER_URL = "https://pmdc.pk/";

const PREFIX = /^(?:(?:PM\s*&\s*DC|PM\s*AND\s*DC|PMDC|PMC|REGISTRATION|REGD?|NUMBER|NO|NUM|ID)\b[\s.:#/-]*)+/;
const NUMBER = /^([0-9]{1,7})\s*[-/\s]?\s*([A-Z]{1,3})$/;

/** The number in the form the register searches on ("12345-P"), or null when it does not fit. */
export function normalizePmdc(raw: string): string | null {
  const dashed = raw.replace(/[‐-—−]/g, "-").toUpperCase().split(/\s+/).filter(Boolean).join(" ");
  const text = dashed.replace(PREFIX, "").replace(/^[ .:#]+|[ .:#]+$/g, "");
  const match = NUMBER.exec(text);
  if (!match) return null;
  const suffix = match[2];
  const number = parseInt(match[1], 10); // the register has no leading zeros
  const known = (PMDC_SUFFIXES as readonly string[]).includes(suffix);
  return known && number >= 1 && number <= 9_999_999 ? `${number}-${suffix}` : null; // checked after the zeros go
}

/**
 * PMDC registration numbers. Mirrors backend/services/pmdc.py (normalize_registration), which checks again.
 *
 * The PMDC register searches an exact number in the form `12345-P`: digits, a hyphen and one letter
 * (letters seen: P, N, S, D). "12345P", "12345/P" and "12345" find nothing there, so a number is written
 * in that form before it is saved.
 */
export const PMDC_EXAMPLE = "12345-P";
export const PMDC_FORMAT_HELP = `Enter the number as printed on your PMDC certificate: digits, a dash and a letter, for example ${PMDC_EXAMPLE}.`;
/** The PMDC page where anyone can look a doctor up by registration number. */
export const PMDC_REGISTER_URL = "https://pmdc.pk/";

const PREFIX = /^(?:(?:PM\s*&\s*DC|PM\s*AND\s*DC|PMDC|PMC|REGISTRATION|REGD?|NUMBER|NO|NUM|ID)\b[\s.:#/-]*)+/;
const NUMBER = /^([0-9]{3,7})\s*[-/\s]?\s*([A-Z])$/;

/** The number in the form the register searches on ("12345-P"), or null when it does not fit. */
export function normalizePmdc(raw: string): string | null {
  const dashed = raw.replace(/[‐-—−]/g, "-").toUpperCase().split(/\s+/).filter(Boolean).join(" ");
  const text = dashed.replace(PREFIX, "").replace(/^[ .:#]+|[ .:#]+$/g, "");
  const match = NUMBER.exec(text);
  if (!match) return null;
  const digits = String(parseInt(match[1], 10)); // the register has no leading zeros
  return digits.length >= 3 && digits.length <= 7 ? `${digits}-${match[2]}` : null; // counted after the zeros go
}

/** Number formats shared by every page. Missing values show an en dash. */
const DASH = "–";
export const MINUS = "−"; // U+2212, the same width as + in tabular figures

export const pct = (v: number | null): string => (v == null ? DASH : `${v.toFixed(1)}%`);

/** A change in percentage points: "+3.1 pts" / "−6.4 pts". */
export function points(v: number | null): string {
  if (v == null) return DASH;
  const r = Math.round(v * 10) / 10; // rounded first, so -0.04 is "+0.0 pts", never "−0.0 pts"
  return `${r < 0 ? MINUS : "+"}${Math.abs(r).toFixed(1)} pts`;
}

/** The report bands: 70% and up is high, 40% to under 70% mid, below 40% low. */
export const band = (rate: number): "hi" | "mid" | "lo" => (rate >= 70 ? "hi" : rate >= 40 ? "mid" : "lo");

/** How many of the meter's five bars are filled. */
export const meterBars = (rate: number): number => Math.min(5, Math.max(0, Math.round(rate / 20)));

export const int = (v: number): string => v.toLocaleString("en-GB");

/** The sign shown before a signed number: "+", U+2212 "−" (not a hyphen) or nothing for zero. Decided after rounding
 *  to `digits` places (the format's maximumFractionDigits, default 3), so -0.04 at 1 decimal has no sign. */
export const signOf = (v: number, digits = 3): string => {
  const r = Math.round(Math.abs(v) * 10 ** digits); // of the magnitude, so -0.05 rounds away from zero like +0.05
  return r === 0 ? "" : v < 0 ? MINUS : "+";
};

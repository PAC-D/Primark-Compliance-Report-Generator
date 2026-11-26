/** The Supplier Compliance filters, kept in the URL so a filtered view can be shared and survives a reload. */
export const BANDS = ["all", "high", "mid", "low"] as const;
export type Band = (typeof BANDS)[number];

export type Filters = {
  month: string; // "YYYY-MM"; "" means the latest month with data
  region: string; // "BD" | "CN" | "" for any
  country: string;
  supplier: string; // part of the name
  factory: string; // part of the name
  approved_by: string; // KPI page: one approver
  band: Band; // filters the table on the page
  page: number; // 1-based, 25 rows a page
};

const MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;

/** The shared ?month= ("YYYY-MM"), or null when it is missing or invalid (the page then uses the latest month). */
export const monthFrom = (search: URLSearchParams): string | null => {
  const m = search.get("month")?.trim() ?? "";
  return MONTH.test(m) ? m : null;
};

/** A tab's path carrying the month, e.g. withMonth("/kpi", "2026-08") -> "/kpi?month=2026-08". */
export const withMonth = (path: string, month: string | null): string =>
  month ? `${path}?month=${encodeURIComponent(month)}` : path;

/** "2026-08" moved by n months: addMonths("2026-01", -1) -> "2025-12". */
export function addMonths(m: string, n: number): string {
  const d = new Date(`${m}-01T00:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() + n);
  return d.toISOString().slice(0, 7);
}

/** "2026-08" -> "August 2026" (or other parts with opts). */
export const monthName = (m: string, opts: Intl.DateTimeFormatOptions = { month: "long", year: "numeric" }): string =>
  new Date(`${m}-01T00:00:00Z`).toLocaleDateString("en-GB", { ...opts, timeZone: "UTC" });

const TEXT = ["month", "region", "country", "supplier", "factory", "approved_by"] as const;

export function readFilters(search: URLSearchParams): Filters {
  const band = search.get("band") as Band;
  const page = Number(search.get("page"));
  const text = Object.fromEntries(TEXT.map((k) => [k, search.get(k)?.trim() ?? ""])) as Record<(typeof TEXT)[number], string>;
  const supplier = search.get("supplier") ?? "";
  text.supplier = supplier.trim() ? supplier : ""; // an exact name: " X " must reach the API as it is; all spaces is none
  text.region = ["BD", "CN"].includes(text.region.toUpperCase()) ? text.region.toUpperCase() : ""; // anything else is all regions
  if (!MONTH.test(text.month)) text.month = ""; // a bad month means the latest
  return { ...text, band: BANDS.includes(band) ? band : "all", page: Number.isInteger(page) && page > 1 ? page : 1 };
}

/** The query string for `f`, without defaults. Spaces are %20 (as encodeURIComponent writes them), not "+". */
export function writeFilters(f: Filters): string {
  const pairs: [string, string][] = TEXT.filter((k) => f[k]).map((k) => [k, f[k]]);
  if (f.band !== "all") pairs.push(["band", f.band]);
  if (f.page > 1) pairs.push(["page", String(f.page)]);
  return pairs.map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&");
}

/** A supplier's Supplier Compliance page for a month (encodes &, spaces, …; readFilters reads it back). */
export const supplierPath = (supplier: string, month: string | null): string =>
  `/supplier-compliance?${writeFilters({ ...readFilters(new URLSearchParams()), month: month ?? "", supplier })}`;

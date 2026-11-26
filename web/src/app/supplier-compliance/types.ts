/** GET /api/supplier: json_safe(report_context(supplier, month, transactions=False)) from tps/reports/supplier_report.py. */
import type { LineCounts } from "../dashboard/types";

export type BandKey = "high" | "mid" | "low";

export type SupplierReport = {
  supplier_name: string;
  month_name: string;
  year: number;
  kpis: { origin_country: string; factory_count: number; total_lines: number; compliant_count: number; non_compliant_count: number };
  ranking: number;
  total_suppliers: number;
  shared: boolean;
  local_rankings: { country: string; rank: number; total: number; shared: boolean }[];
  compliance_rate: number;
  band: BandKey;
  factory_bands: Partial<Record<BandKey, number>>; // a Counter: a band with no factories is missing
  monthly_compliance_scores: (number | null)[];
  monthly_compliance_labels: string[];
  standard_carton_scores: (number | null)[];
  standard_carton_labels: string[];
  density_scores: (number | null)[];
  density_labels: string[];
  associated_factories: { factory: string; origin_countries: string; compliance_rate: number; band: BandKey }[];
  line_details: (LineCounts & { factory: string })[];
  line_totals: LineCounts;
  compliance_data: { factory: string; standard_carton_pct: number; total_carton_qty: number; corrugated_sqm: number }[];
};

/** GET /api/supplier-transactions: one row per line (TRANSACTION_COLUMNS in tps/metrics/supplier.py), only what the table shows. */
export type Transaction = {
  origin_country: string | null; factory: string | null; destination_po: string | null; kimball: string | null; size: string | null;
  po_qty: number | null; handover_date: string | null; units_per_carton: number | null;
  carton_length_mm: number | null; carton_width_mm: number | null; carton_height_mm: number | null;
  packaging_supplier: string | null; updated_date: string | null; approved_date: string | null;
  packaging_status: string | null; compliance_status: string | null;
};
export type TransactionPage = { rows: Transaction[]; total: number; page: number; page_size: number };

export type SearchResult = { suppliers: string[]; factories: { factory: string; suppliers: string[] }[] };

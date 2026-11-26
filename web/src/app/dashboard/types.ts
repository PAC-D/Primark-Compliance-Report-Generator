/** GET /api/dashboard: json_safe(summary_context(month)) from tps/reports/summary_excel.py. */
export type LineCounts = { dest_po_count: number; reflected_lines: number; pending: number; approved: number; rejected: number; escalated: number };

export type Dashboard = {
  sources: { total_suppliers: number; total_factories: number };
  compliance_data: { country: string; compliance_rate: number }[];
  country_data: Record<string, (number | null)[]>; // by country, one rate per chart label
  chart_labels: string[]; // "Jan '26", …
  country_order: string[];
  line_details: (LineCounts & { country: string })[];
  line_totals: LineCounts;
  top_suppliers: {
    sl: number; supplier: string; origin_countries: string; factory_count: number; dest_po_count: number;
    reflected_lines: number; compliance_rate: number;
  }[];
  suppliers_below: {
    sl: number; supplier: string; origin_country: string; factory_count: number; dest_po_count: number; qty: number;
    reflected_lines: number; compliance_rate: number | null; prev_1_rate: number | null; prev_2_rate: number | null; avg_3month: number | null;
  }[];
  email_map: Record<string, string>; // lowercase supplier -> "a@x, b@y"
  all_supplier_trend: { supplier: string; rates: (number | null)[] }[];
  month_labels: string[];
  working_days: number;
  days_in_month: number;
  month_name: string;
  year: number;
};

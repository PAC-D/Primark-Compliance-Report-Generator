# KPI Report + Clear Database — Design

**Date:** 2026-08-04
**Status:** Approved (Option A)

## 1. Goal

Add two new features to the TPS pipeline without modifying any existing behavior:

1. A **Clear Database** menu option that deletes all rows from the data tables (keeps the tables themselves).
2. A **KPI Report** — a single PDF across all countries — reusing the TPS report header structure but titled **"Transit Packaging System (TPS) KPI Report"**.

## 2. Scope

### 2.1 Clear Database

- New menu entry (option 8): prompts for confirmation, then deletes all rows from `raw_data` and `supplier_emails`.
- Tables are kept; only data is removed.
- New functions in `database.py` (additive, no existing code changed):
  - `clear_raw_data()` — `DELETE FROM raw_data`
  - `clear_all_tables()` — `DELETE FROM raw_data` + `DELETE FROM supplier_emails`

### 2.2 KPI Report (PDF)

Report month **M** = user-selected month (default = previous month, same prompt pattern as existing reports).

| # | Section | Content |
|---|---------|---------|
| 1 | Header | Same as TPS report (Primark/Allport logos, red accent bar, footer). Title: "Transit Packaging System (TPS) KPI Report" + month/year |
| 2 | 3 monthly tables | One table each for **M**, **M-1**, **M last year**. Columns: Country \| No. of Suppliers \| No. of Factories \| Reflected Lines. **Skip any table whose month has no data.** |
| 3 | Individual performance | Rows = distinct `approved_by`; columns = line counts for M, M-1, M-last-year |
| 4 | Avg lines / day (M, i.e. previous month) | Two blocks: **BD region** (Bangladesh, India, Pakistan, Sri Lanka, Morocco, Turkey) and **CN region** (all other countries: China, Cambodia, Vietnam). Formula per block: `SUM(lines WHERE packaging_status != 'Pending') / working_days`. Working days: BD region excludes Fri+Sat; CN region excludes Sat+Sun |
| 5 | Charts (12 months ending at M) | Line chart: suppliers + factories per month. Line/bar chart: reflected lines BD region per month. Line/bar chart: reflected lines CN region per month |

### 2.3 Region definitions

- **BD region countries**: Bangladesh, India, Pakistan, Sri Lanka, Morocco, Turkey (full names verified against live DB).
- **CN region countries**: everything else (currently China, Cambodia, Vietnam). Reuse `CN_REGION_COUNTRIES` set semantics.

## 3. Architecture (Option A — new modules, additive)

| File | Purpose |
|------|---------|
| `tps-pipeline/kpi_metrics.py` | All KPI SQL queries (session-based, mirrors `metrics.py` patterns) |
| `tps-pipeline/kpi_renderer.py` | `render_kpi_report(report_month) -> str` (full HTML), loads `templates/kpi_report.html.j2` |
| `tps-pipeline/templates/kpi_report.html.j2` | Jinja2 template, header + tables + Chart.js charts |
| `tps-pipeline/database.py` | (edit, additive only) `clear_raw_data()`, `clear_all_tables()` — already drafted |
| `tps-pipeline/menu.py` | (edit, additive only) option 7 → KPI report handler, option 8 → clear DB handler, banner lines |

No changes to: `renderer.py`, `summary_renderer.py`, `summary_excel_renderer.py`, `metrics.py`, `processor.py`, existing templates, or existing menu handlers.

## 4. KPI Metrics Functions (`kpi_metrics.py`)

All queries read `raw_data` only, using `handover_date` month ranges like existing metrics.

- `get_kpi_monthly_tables(report_month) -> list[dict]` — for each of [M, M-1, M-last-year]: `{month_start, month_label, rows: [{country, suppliers, factories, reflected_lines}]}`; months with zero rows excluded.
- `get_kpi_approved_by_performance(report_month) -> dict` — `{month_label: {approved_by: line_count}}` for the 3 months; rows = union of distinct approved_by.
- `get_kpi_avg_lines_per_day(report_month) -> dict` — `{bd: {lines, working_days, avg}, cn: {...}}` for month M. BD lines = sum where `origin_country IN (BD set) AND packaging_status != 'Pending'`; CN = same for all other countries. Working days computed with `calendar`: BD → days excluding Fri+Sat; CN → days excluding Sat+Sun.
- `get_kpi_supplier_factory_trend(report_month) -> tuple[labels, supplier_counts, factory_counts]` — 12 months ending at M (same range logic as `_get_chart_month_range_for_all`).
- `get_kpi_region_reflected_lines(report_month) -> dict` — `{region: {month_start: count}}` for BD and CN regions over the 12-month range.

Reuse `get_last_day_of_month`, `get_report_month`, `get_session` from `metrics.py`/`database.py` where possible.

## 5. Template & Rendering

- `kpi_report.html.j2`: same page header markup as `report.html.j2` (logos, red accent bar), title block "Transit Packaging System (TPS) KPI Report", report period. Charts rendered with Chart.js (loaded from CDN, same as existing template), rendered via inline JSON like existing charts.
- `kpi_renderer.render_kpi_report()` builds context dict (month labels, tables, performance, avg/day, chart data) and renders template. PDF conversion via existing `pdfgen.html_to_pdf`.
- Output path: `output/KPI_Report_<Month_Year>.pdf` (uses `config["paths"]["output_dir"]`).

## 6. Error Handling

- If no data exists at all → print message and abort (no empty PDF).
- Individual monthly tables with no data → omitted (per requirement).
- DB errors → log + friendly message (same pattern as `handle_generate_summary_report`).
- Clear DB: confirmation prompt; cancel = no-op.

## 7. Testing

- Unit tests for `kpi_metrics` using the same style as `tests/test_metrics.py` (mock session / real DB if available): monthly table month range, skip-empty behavior, BD/CN classification, working-day denominators, avg formula, 12-month label range.
- Manual test: run `menu.py`, option 7 with default month; verify PDF sections; option 8 clears rows and keeps tables.

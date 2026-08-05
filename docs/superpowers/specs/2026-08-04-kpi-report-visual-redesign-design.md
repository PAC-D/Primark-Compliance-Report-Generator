# KPI Report Visual Redesign — Design

Date: 2026-08-04
Scope: visual/layout changes to the KPI report PDF plus two small metrics/behavior changes.

## Current behaviour

- 3 monthly summary tables render vertically, full-width, one after another.
- Individual Performance section titled "Individual Performance (Approved By)".
- Performance table always shows 3 month columns (M, M-1, M-last-year) even when a
  month has no data (zero-filled).
- Average lines per day uses `round(x, 2)` (nearest, 2 decimals).
- 12-month charts follow the avg blocks on the same page.

## Changes

### 1. Monthly Summary — 3 cards across one row
- One horizontal row of 3 cards. Each card has the month label as a card title and a
  compact table inside (Country / Suppliers / Factories / Reflected Lines), using a
  smaller font so the row fits A4 portrait.
- Cards keep the existing style language (rounded border, section color) used elsewhere
  in the report.

### 2. Individual Performance section
- Section title becomes just "Individual Performance" — drop " (Approved By)".
- The first column header remains "Approved By".

### 3. Skip months with no data (same rule as monthly summary)
- The performance month columns must only include months that exist in the database,
  aligned with the months shown by the monthly-summary cards. No zero-filled ghost
  columns.

### 4. Average lines per day — ceil to whole number
- Change metric to `math.ceil(lines / days)` (0 when days == 0). e.g. 6025 / 23 =
  262 (was 261.96).

### 5. Charts on their own page
- Insert a CSS page break before the charts section. All 3 charts stack full-width on
  the page after the tables.

### 6. Page size
- Already A4 portrait in the template (`@page`) and `pdfgen.html_to_pdf`. No change.

## Files touched

- `tps-pipeline/templates/kpi_report.html.j2` — card layout, title text, page break,
  full-width charts.
- `tps-pipeline/kpi_metrics.py` — `get_kpi_approved_by_performance` month filtering;
  `get_kpi_avg_lines_per_day` ceil rounding.
- `tps-pipeline/tests/test_kpi_metrics.py` — updated expectations.
- `tps-pipeline/tests/test_kpi_renderer.py` — updated title assertion.

## Verification

- Full unit suite green (`..\..\.venv-win\Scripts\python.exe -m pytest tests -v`).
- Regenerate `output/KPI_Report_<Month>_<Year>.pdf` against the database and inspect
  the rendered pages for the row of 3 cards, revised title, single charts page, and
  A4 size.
- Note: the database was emptied during the Task 11 clear-db verification; re-import
  data before regenerating the PDF.
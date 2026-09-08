# TPS Compliance Reporting System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A Python pipeline that loads Excel transaction data into PostgreSQL, generates per-supplier PDF compliance reports using Jinja2 + Playwright, and provides a text menu.

**Architecture:** Linear ETL pipeline with menu-driven actions. Playwright renders HTML (inline SVG charts + external CSS) to PDF. Reports generated per supplier per month.

**Tech Stack:** Python 3 · pandas + openpyxl · PostgreSQL + SQLAlchemy · Jinja2 · Playwright

---

## Project Structure

```
tps-pipeline/
├── menu.py
├── processor.py
├── database.py
├── metrics.py
├── renderer.py
├── pdfgen.py
├── config.yaml
├── config/table_columns.yaml
├── templates/report.html.j2
├── templates/report.css
├── data/
├── output/
├── tests/
│   ├── test_processor.py
│   ├── test_metrics.py
│   └── test_renderer.py
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `tps-pipeline/config.yaml`
- Create: `tps-pipeline/config/table_columns.yaml`
- Create: `tps-pipeline/data/` (directory)
- Create: `tps-pipeline/output/` (directory)
- Create: `tps-pipeline/tests/__init__.py`
- Create: `tps-pipeline/__init__.py`

- [ ] Create directory structure
- [ ] Create config.yaml with DB connection, paths, report_month_offset: 1
- [ ] Create table_columns.yaml with all 18 Page 3 columns
- [ ] Create empty __init__.py files

---

## Task 2: Database Setup

**Files:**
- Create: `tps-pipeline/database.py`

- [ ] Write database.py with SQLAlchemy engine, Session, init_db()
- [ ] init_db() creates raw_data table with all columns including derived: carton_type, cbm, density, compliance_status
- [ ] init_db() creates suppliers table
- [ ] Add SUPPLIER_NORMALISATION dict and normalise_supplier() function

---

## Task 3: ETL Processor

**Files:**
- Create: `tps-pipeline/processor.py`

- [ ] Write load_excel() — read Excel, drop columns, rename, clean, derive
- [ ] Derive: carton_type (Standard/Custom from carton_matrix_code)
- [ ] Derive: cbm = (L/1000)*(W/1000)*(H/1000) with 4 decimal places
- [ ] Derive: density = units_per_carton / cbm with 2 decimal places
- [ ] Derive: compliance_status per spec logic (Approved + dates check)
- [ ] Strip whitespace from all text columns
- [ ] Write process_file() — load_excel + insert all rows to DB
- [ ] Write is_file_processed() — check data/ by filename + mtime
- [ ] Write copy_to_data() — copy processed file to data/

---

## Task 4: Metrics Calculations

**Files:**
- Create: `tps-pipeline/metrics.py`

- [ ] Write get_report_month() — returns first day of previous calendar month
- [ ] Write get_compliance_rate(supplier, year, month)
- [ ] Write get_monthly_compliance_scores(supplier, months=12) — trailing 12 months
- [ ] Write get_standard_carton_scores(supplier, months=12) — Approved rows only
- [ ] Write get_density_scores(supplier, months=12) — Approved rows only
- [ ] Write get_global_ranking(supplier) — DENSE_RANK, return (rank, total, shared)
- [ ] Write get_supplier_kpis(supplier) — origin_country, factory_count, total_lines, compliant_count, non_compliant_count
- [ ] Write get_factory_breakdown(supplier) — all 4 factory tables data
- [ ] Write get_transactions(supplier) — raw rows sorted by handover_date, updated_date

---

## Task 5: Report Template (HTML + CSS)

**Files:**
- Create: `tps-pipeline/templates/report.css`
- Create: `tps-pipeline/templates/report.html.j2`

- [ ] Write report.css with all styles per spec:
  - Variables: --bg #fff, --accent-red #e31837, --accent-sky #87ceeb
  - Page header (logos left/right, red bottom border)
  - Info cards with left border accent
  - Chart containers (gauge, bar charts, line chart)
  - Table styles with alternating rows
  - Status color classes (green/orange/red)
  - @page rules for portrait/landscape

- [ ] Write report.html.j2 — 3-page structure:
  - Page 1: Header, title, supplier block, 3 info cards, gauge, 2 bar charts, line chart
  - Page 2: Factory breakdown (4 sections)
  - Page 3+: Transaction table (config-driven columns, landscape)
  - SVG chart functions embedded in template
  - CSS loaded via <link> tag

---

## Task 6: Renderer — Jinja2 to HTML

**Files:**
- Create: `tps-pipeline/renderer.py`

- [ ] Write render_report(supplier, metrics, transactions, output_path)
- [ ] Load config/table_columns.yaml for Page 3 column definitions
- [ ] Render report.html.j2 with all data passed in
- [ ] Return rendered HTML string
- [ ] Inline SVG charts generated in template using Jinja2 loops

---

## Task 7: PDF Generation

**Files:**
- Create: `tps-pipeline/pdfgen.py`

- [ ] Write html_to_pdf(html_content, output_path) using Playwright
- [ ] Chromium browser with headless=True
- [ ] page.setContent() with the HTML
- [ ] page.pdf() with: printBackground=True, format='A4'
- [ ] Return True on success, False on failure

---

## Task 8: Menu System

**Files:**
- Create: `tps-pipeline/menu.py`

- [ ] Display menu: [1] Process New File, [2] Generate Reports, [3] View Logs, [0] Exit
- [ ] [1] Process: tkinter filedialog, check is_file_processed, process_file, copy_to_data, log
- [ ] [2] Generate: for each supplier with data this month, render + pdfgen, save to output/
- [ ] [3] View Logs: print last 50 lines from logs/run.log
- [ ] [0] Exit: print goodbye, exit

---

## Task 9: Logging

**Files:**
- Create: `tps-pipeline/logging_config.py`
- Modify: All modules to use logger

- [ ] Setup logger to logs/run.log with timestamp + level + message
- [ ] Log: file processed (filename, row count), report generated per supplier, errors

---

## Task 10: Tests

**Files:**
- Create: `tps-pipeline/tests/test_processor.py`
- Create: `tps-pipeline/tests/test_metrics.py`
- Create: `tps-pipeline/tests/test_renderer.py`

- [ ] test_load_excel_with_derived_columns — verify carton_type, cbm, density, compliance_status
- [ ] test_compliance_status_logic — Approved + valid dates = Compliant
- [ ] test_global_ranking_calculation — DENSE_RANK logic
- [ ] test_render_html_with_all_sections — template renders without errors


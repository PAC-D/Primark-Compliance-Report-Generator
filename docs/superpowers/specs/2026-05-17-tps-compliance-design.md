# TPS Compliance Reporting System — Design Spec
**Date:** 2026-05-17
**Status:** Approved

---

## 1. Overview

Automated monthly reporting pipeline that generates PDF compliance reports per supplier from Excel transaction data. One run generates all reports, no manual per-supplier work.

---

## 2. Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3 |
| ETL | pandas, openpyxl |
| Database | PostgreSQL + SQLAlchemy |
| Templating | Jinja2 → HTML + external CSS |
| PDF Generation | Playwright (Chromium browser) |
| Charts | Inline SVG (generated in Jinja2 templates) |
| UI | Terminal menu (text-based) |

---

## 3. Project Structure

```
tps-pipeline/
├── menu.py              # Entry point — text menu
├── processor.py         # File selection, deduplication, ETL, copy to data/
├── database.py          # DB connection, schema setup, queries
├── metrics.py           # All metric calculations
├── renderer.py          # Jinja2 → HTML with inline SVG charts
├── pdfgen.py            # Playwright browser → PDF
├── config/
│   └── table_columns.yaml   # Page 3 column definitions (config-driven)
├── templates/
│   ├── report.html.j2      # Three-page HTML template
│   └── report.css          # External stylesheet
├── data/                    # Processed Excel files stored here
├── output/                  # Generated PDFs
└── logs/                    # Run logs with timestamps
```

---

## 4. Visual Style

| Element | Value |
|---------|-------|
| Background | `#ffffff` (white) |
| Primary accent | `#e31837` (Primark red) |
| Secondary | `#87ceeb` (skyblue) |
| Text primary | `#1a1a1a` |
| Text secondary | `#666666` |
| Status: Approved/Compliant | `#16a34a` (green) |
| Status: Pending/Escalated | `#ea580c` (orange) |
| Status: Rejected/Non-compliant | `#dc2626` (red) |
| Chart gradient | `#e31837` → `#87ceeb` |

---

## 5. Database Schema

### Table: `raw_data`

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PRIMARY KEY | |
| area | TEXT | |
| sub_area | TEXT | |
| origin_country | TEXT | |
| origin_port | TEXT | |
| supplier | TEXT | Normalised name |
| factory | TEXT | |
| destination_po | TEXT | |
| kimball | TEXT | |
| description | TEXT | |
| colour_code | TEXT | |
| size | TEXT | |
| po_qty | INTEGER | NULL if empty |
| handover_date | DATE | Time component stripped |
| carton_matrix_code | TEXT | |
| units_per_carton | INTEGER | NULL if empty |
| carton_length_mm | INTEGER | NULL if empty |
| carton_width_mm | INTEGER | NULL if empty |
| carton_height_mm | INTEGER | NULL if empty |
| packaging_supplier | TEXT | |
| updated_date | TIMESTAMPTZ | |
| updated_by | TEXT | |
| approved_date | TIMESTAMPTZ | |
| approved_by | TEXT | |
| packaging_status | TEXT | |
| source_file | TEXT | Filename for audit trail |
| carton_type | TEXT | "Standard" if carton_matrix_code present, else "Custom" |
| cbm | NUMERIC(10,4) | (L/1000) × (W/1000) × (H/1000), NULL if any dimension missing |
| density | NUMERIC(10,2) | units_per_carton / cbm, NULL if cbm missing |
| compliance_status | TEXT | "Compliant" or "Non-compliant" |

### Table: `suppliers`

| Column | Type |
|--------|------|
| supplier_name | TEXT PRIMARY KEY |
| email | TEXT |

---

## 6. Supplier Name Normalisation

Applied before any processing:

| Raw Name | Normalised To |
|----------|---------------|
| WEIHAI BETTEX INTERNATIONAL TRADING CO., LTD | BETTEX (HK) LIMITED (80243) |
| YIWU HONGZHOU IMPORT & EXPORT CO LTD | HOME JOY TEXTILE CO. LIMITED (82056) |
| HIGH HOPE INTERNATIONAL G | JIANGSU HUAJING INTERNATIONAL TRADE CO LTD (80070) |
| ZHEJIANG ZHUJI IMP&EXP CO LTD | ZHEJIANG LIJIA FOREIGN TRADE CO LTD (82990) |
| BODYLINE (PRIVATE) LIMITED | BODYLINE TRADING (PRIVATE) LIMITED (67247) |
| PENTI CORAP SANAYI VE TICARET AS | PENTI GIYIM TICARET A.S (80651) |
| FUZHOU BICANO TRADING CO. LIMITED | HONG KONG DIJIA TUO TECHNOLOGY CO., LIMITED (83666) |
| TEXPORT SYNDICATE LIMITED | TEXPORT SYNDICATE PRIVATE LIMITED (83002) |
| JADE FOOTWEAR CO LTD | ABUNDANT GRACE LIMITED (80064) |
| SAIDE TEKSTIL | SAIDE GROUP DIS TICARET AS (80111) |

---

## 7. Compliance Status Logic

```
"Compliant" IF ALL of:
  1. packaging_status = "Approved" (exact, case-sensitive)
  2. handover_date IS NOT NULL
  3. updated_date IS NOT NULL
  4. updated_date <= handover_date

Otherwise → "Non-compliant"
```

---

## 8. Report Structure

### Page 1 — Dashboard (Portrait)

- **Header:** PRIMARK logo (left), partner logos (right)
- **Title:** "TPS Compliance Report" + month name + release date
- **Supplier block:** Bold supplier name, "Supplier" label in skyblue
- **3 info cards:** Origin Country, No of Factories, Global Ranking
- **Gauge:** Semicircle, 0-100%, gradient fill, compliance rate
- **Bar chart:** Monthly Compliance Score (12 months)
- **Bar chart:** Use of Standard Carton (12 months, Approved rows only)
- **Line chart:** Product Density (12 months, Approved rows only)

Layout: Gauge + Standard Carton bar (top row), Compliance bar + Density line (bottom row)

### Page 2 — Factory Breakdown (Portrait)

4 tables per factory:
1. Associated Factories (SI, Factory, Origin Countries, Compliance Rate)
2. Line Details (Factory, Dest PO count, Reflected Lines, Pending/Approved/Rejected/Escalated counts)
3. Compliance (Compliance Rate, Standard Carton %, Total Carton Qty, Corrugated Board SQM)
4. Product Density (Avg Unit/Carton, Unit/CBM)

### Page 3+ — Transaction Table (Landscape)

- All raw rows for that supplier/month
- Columns driven by `config/table_columns.yaml`
- Header repeats on every page
- Alternating row colors
- Page numbers in footer
- Color-coded status columns
- Ordered by: Current Handover Date → Updated Date

### Default Page 3 Columns

| Column | Alignment | Notes |
|--------|-----------|-------|
| Origin Country | left | |
| Origin Port | left | |
| Factory | left | |
| Destination PO | left | |
| Kimball | left | |
| Description | left | |
| Colour | left | |
| Size | left | |
| PO Qty | center | |
| Current Handover Date | center | |
| Units Per Carton | center | |
| L×W×H (mm) | center | Displayed as "700×460×300" |
| Packaging Supplier | left | |
| Updated Date | center | |
| Updated By | left | |
| Approved Date | center | |
| Packaging Confirmation Status | center | Color coded |
| Compliance Status | center | Color coded |

---

## 9. Metrics Calculations

All metrics use `handover_date` for month grouping. Report month = previous calendar month.

| Metric | Formula |
|--------|---------|
| Compliance Rate | (Compliant rows / Total rows) × 100, 2dp |
| Monthly Compliance Score (12-month) | Same formula per month, 0 if no data |
| Standard Carton % (12-month) | (Standard rows / Total rows) × 100, Approved only, 1dp |
| Product Density (12-month) | AVG(density), Approved only, rounded to integer |
| Global Ranking | DENSE_RANK() descending by compliance rate |
| Origin Country (supplier) | MODE() of origin_country for the month |
| No of Factories | COUNT(DISTINCT factory) |
| Corrugated Board SQM | Σ((L+6)×(W+H+4)×2 / 10000) per factory, NULL dims skipped |

---

## 10. Program Flow

### Menu Options

```
[1] Process New File
    → Open file picker (tkinter)
    → Check if file already in data/ (by filename + modified date)
    → If new: clean → derive columns → insert to DB
    → Copy file to data/
    → Log: timestamp, filename, row count, result

[2] Generate Reports
    → Determine report month (previous calendar month)
    → For each supplier in DB with data for that month:
        → Calculate all metrics
        → Render HTML (Jinja2 + SVG charts + CSS)
        → Playwright page.pdf() → PDF
        → Save to output/{supplier}_{date}.pdf
    → Log each supplier result

[3] View Logs
    → Print recent log entries (last 50 lines)

[0] Exit
```

### Deduplication Logic

Before processing: check if a file with the same name AND modified date already exists in `data/`. If identical name but different modified date → process anyway (new version). If identical name AND identical modified date → skip, already processed.

---

## 11. Columns to Drop During ETL

These exist in the raw Excel but are not stored:
- Carton Specification(s)
- Priority
- Pack Type
- Pallet Plan(s)
- Container Plan(s)
- Dialog(s)
- ProductSKULine
- Colour Code

---

## 12. Data Cleaning Rules

- `handover_date`: Strip time component, store as DATE
- `updated_date`, `approved_date`: Store as TIMESTAMPTZ, keep full timestamp
- `po_qty`, `units_per_carton`, `carton_length_mm`, `carton_width_mm`, `carton_height_mm`: Convert to INTEGER, empty cells → NULL
- `density`: Convert to NUMERIC(10,2), empty cells → NULL, calculated after CBM
- All text columns: STRIP leading/trailing whitespace

---

## 13. Error Handling

| Situation | Action |
|-----------|--------|
| Supplier in data, no email | Skip, log warning |
| NULL carton dimensions | Excluded from SQM calc only, counted in all other metrics |
| Month with no data | Show as 0% or 0 in charts, not omitted |
| Calculation failure | Log error, skip supplier, continue pipeline |

---

## 14. PDF Generation

- Playwright `chromium` browser
- `page.pdf()` with `printBackground: true`
- Page 1-2: `@page { size: A4 portrait }`
- Page 3+: `@page { size: A4 landscape }` via `page-break-before: always`
- External CSS file loaded via `page.goto()` with `waitUntil: 'networkidle'`
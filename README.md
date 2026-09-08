# Primark Compliance Report Generator

Automated tooling for PAC-D's monthly Primark packaging-management compliance
reporting: ingest bi-weekly transaction exports, load them into a database,
and generate per-supplier compliance PDFs, Excel/PDF summary reports, and
KPI reports — all from a single text menu.

## Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Usage](#usage)
  - [tps-pipeline menu](#tps-pipeline-menu)
  - [Standalone extractors](#standalone-extractors)
- [Testing](#testing)
- [Data & Confidentiality](#data--confidentiality)
- [Project Docs](#project-docs)
- [License](#license)

## Overview

Primark's packaging-management team exports raw transaction data as
bi-weekly Excel files (one per half-month, per region). This project turns
those exports into the reporting suppliers and account managers actually
need:

- a three-page PDF compliance report per supplier, per month
- a workbook and PDF summarizing every supplier for the month
- a KPI report with regional and trend charts across all suppliers
- one-off tools to re-slice the raw data by month or by supplier, when a
  report is needed outside the normal pipeline

Everything is driven from a terminal menu (`tps-pipeline/menu.py`) backed by
a local PostgreSQL database — no manual per-supplier work.

## Repository Structure

```
.
├── tps-pipeline/              # Main pipeline: ingest -> DB -> reports (menu-driven CLI)
│   ├── menu.py                 # Entry point
│   ├── processor.py            # File selection, dedup, ETL into the DB
│   ├── database.py             # DB connection, schema, queries, supplier-name normalisation
│   ├── metrics.py / kpi_metrics.py   # Metric calculations for compliance / KPI reports
│   ├── renderer.py / summary_renderer.py / summary_excel_renderer.py / kpi_renderer.py
│   │                            # Jinja2 -> HTML (inline SVG charts) / Excel rendering
│   ├── pdfgen.py                # Playwright (headless Chromium) HTML -> PDF
│   ├── config/table_columns.yaml   # Config-driven report table columns
│   ├── templates/               # HTML + CSS report templates
│   ├── assets/                  # Logos and images used in reports
│   ├── tests/                   # pytest suite
│   ├── requirements.txt
│   └── config.yaml.example      # Copy to config.yaml and fill in local DB credentials
├── monthly-data-extractor/    # Combines every bi-weekly file for a month into one workbook
│   └── monthly-data-extractor.py  # (duplicated at repo root for convenience)
├── supplier-data-extractor/   # Splits bi-weekly files into one workbook per supplier,
│   │                            # grouped into BD Region / CN Region folders
│   └── extract_supplier_data.py
└── docs/superpowers/           # Design specs and implementation plans for each feature
    ├── specs/
    └── plans/
```

`monthly-data-extractor` and `supplier-data-extractor` both read their
source files from `tps-pipeline/data/`, so `tps-pipeline` must be present
and populated for either to run.

## Tech Stack

| Layer         | Technology                              |
|---------------|------------------------------------------|
| Language      | Python 3.11+ (developed with 3.14)       |
| ETL           | pandas, openpyxl                         |
| Database      | PostgreSQL via SQLAlchemy                |
| Templating    | Jinja2 → HTML, external CSS              |
| Charts        | Inline SVG (generated in templates)      |
| PDF rendering | Playwright (headless Chromium)           |
| Config        | YAML                                     |
| Tests         | pytest                                   |
| UI            | Terminal menu (no web/GUI, aside from native file-picker dialogs) |

## Prerequisites

- Python 3.11+
- PostgreSQL, running locally or reachable over the network
- The Playwright Chromium browser binary (installed as part of setup below)

## Setup

```bash
cd tps-pipeline
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp config.yaml.example config.yaml
# edit config.yaml with your local Postgres host/user/password
```

Then create the database and schema. On Linux/macOS with a local `postgres`
superuser available, `setup_db.py` automates this (it also overwrites
`config.yaml` with default `postgres`/`postgres` credentials — edit it
afterwards if you changed them):

```bash
python setup_db.py
```

On Windows, or if you'd rather do it by hand: create a `tps_compliance`
database with your Postgres client of choice, make sure `config.yaml`
points at it, then initialize the schema directly:

```bash
python -c "from database import init_db; init_db()"
```

Once the database exists, launch the pipeline:

```bash
python menu.py
```

## Usage

### tps-pipeline menu

`python menu.py` prints a numbered menu:

| # | Option | What it does |
|---|--------|---------------|
| 1 | Process New File | Pick one or more raw bi-weekly Excel exports via a file dialog, skip/re-process duplicates, load rows into the `raw_data` table, and copy the file into `data/`. |
| 2 | Generate Reports | Pick a month, then render a three-page (portrait + landscape) compliance PDF for every supplier with data that month, sorted into `output/Report_<Month>_<Year>/<BD or CN> Region/`. |
| 3 | Generate Summary Report | Render one Excel workbook summarizing every supplier for the chosen month. |
| 4 | View Logs | Print the last 50 lines of `logs/run.log`. |
| 5 | Extract Supplier Data | Split the raw source files for a chosen month into one workbook per supplier (delegates to `supplier-data-extractor`). |
| 6 | Import Supplier Emails | Load a "Supplier Name / Email" workbook into the database for later use. |
| 7 | Generate KPI Report | Render a PDF with monthly KPI cards plus regional and trend charts across all suppliers. |
| 8 | Clear Database | Delete all rows from `raw_data` and `supplier_emails` (schema is kept), with an option to reload everything from `data/` afterwards. |

### Standalone extractors

These re-slice the same source files in `tps-pipeline/data/` without
touching the database — useful for ad hoc requests outside the normal
reporting cycle.

```bash
# From the repo root
python monthly-data-extractor.py
```
Prompts for a year and month, combines every matching bi-weekly file into a
single `All_Suppliers_<Mon>_<Year>.xlsx` under `monthly-data-extractor/`.

```bash
python supplier-data-extractor/extract_supplier_data.py
```
Prompts for a year and month, and writes one workbook per supplier into
`supplier-data-extractor/output/Data_<Month>_<Year>/<BD or CN> Region/`.

## Testing

```bash
cd tps-pipeline
pytest
```

## Data & Confidentiality

This is a client-facing reporting tool built around real Primark supplier
and packaging-compliance data. To keep that data out of version control,
`.gitignore` excludes:

- `tps-pipeline/data/`, `tps-pipeline/output/`, `tps-pipeline/logs/` — raw source files, generated reports, and run logs
- `supplier-data-extractor/output/`, `monthly-data-extractor/Data_*/` — generated per-supplier/per-month workbooks
- `tps-pipeline/config.yaml` — local database credentials (use `config.yaml.example` as a template)

None of the above are required to read or review the code; they're
recreated locally as the pipeline runs.

## Project Docs

`docs/superpowers/specs/` and `docs/superpowers/plans/` contain the design
specs and implementation plans behind each major feature (TPS compliance
reports, summary reports, KPI reports, supplier email import, info cards).

## License

Proprietary — internal PAC-D project built for Primark. All rights reserved.

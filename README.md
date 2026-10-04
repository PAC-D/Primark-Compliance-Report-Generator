# Primark Compliance Report Generator

Automated tooling for PAC-D's monthly Primark packaging-management compliance
reporting: ingest bi-weekly transaction exports, load them into a database,
and generate per-supplier compliance PDFs, an Excel summary workbook and a
KPI report, all from a single text menu.

## Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Tech Stack](#tech-stack)
- [Setup](#setup)
- [Usage](#usage)
- [Testing](#testing)
- [Data & Confidentiality](#data--confidentiality)
- [Project Docs](#project-docs)
- [License](#license)

## Overview

Primark's packaging-management team exports raw transaction data as
bi-weekly Excel files (one per half-month, per region). This project turns
those exports into the reporting suppliers and account managers need:

- a three-page PDF compliance report per supplier, per month
- an Excel workbook summarizing every supplier for the month
- a KPI report with regional and trend charts across all suppliers
- extracts that re-slice the raw data by month or by supplier, for requests
  outside the normal pipeline

Everything runs from a terminal menu backed by a local PostgreSQL database.

## Repository Structure

```
.
├── tps/                        # The application package
│   ├── __main__.py             # `python -m tps` starts the menu
│   ├── menu.py                 # Text menu (UI only)
│   ├── config.py               # Reads config.yaml; paths; logging setup
│   ├── common.py               # Supplier-name normalisation, regions, month helpers, safe filenames
│   ├── db.py                   # PostgreSQL engine, schema, table maintenance
│   ├── ingest.py               # Transaction-file ETL and supplier-email import
│   ├── extract.py              # Monthly / per-supplier raw-data extracts (no DB)
│   ├── setup_db.py             # One-shot DB creation (Linux/macOS)
│   ├── metrics/
│   │   ├── supplier.py         # Per-supplier report metrics
│   │   ├── summary.py          # All-supplier summary workbook metrics
│   │   └── kpi.py              # KPI report metrics
│   ├── reports/
│   │   ├── supplier_report.py  # Per-supplier report HTML
│   │   ├── summary_excel.py    # Summary workbook (openpyxl)
│   │   ├── kpi_report.py       # KPI report HTML
│   │   ├── html.py             # Jinja environment + embedded logos
│   │   └── pdf.py              # Playwright HTML -> PDF, page numbers
│   ├── templates/              # Jinja2 report templates
│   └── assets/                 # Logos and signature
├── tests/                      # pytest suite
├── docs/superpowers/           # Design specs and implementation plans
├── config.yaml.example         # Copy to config.yaml and fill in DB credentials
├── requirements.txt
└── pytest.ini
```

Created locally at runtime (gitignored): `config.yaml`, `data/` (raw source
files), `output/` (all generated reports and extracts), `logs/`.

## Tech Stack

| Layer         | Technology                              |
|---------------|-----------------------------------------|
| Language      | Python 3.11+ (developed with 3.14)      |
| ETL           | pandas, openpyxl                        |
| Database      | PostgreSQL via SQLAlchemy               |
| Templating    | Jinja2 → HTML with inline SVG charts    |
| PDF rendering | Playwright (headless Chromium), pypdf   |
| Config        | YAML                                    |
| Tests         | pytest                                  |

## Setup

Requires Python 3.11+ and a reachable PostgreSQL server. Run everything from
the repository root.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp config.yaml.example config.yaml   # then set your Postgres host/user/password
```

Create the database and schema. On Linux/macOS with a local `postgres`
superuser, this does both (it overwrites `config.yaml` with default
`postgres`/`postgres` credentials):

```bash
python -m tps.setup_db
```

Otherwise create a `tps_compliance` database by hand, point `config.yaml` at
it, and initialise the schema:

```bash
python -c "from tps.db import init_db; init_db()"
```

## Usage

```bash
python -m tps
```

| # | Option | What it does |
|---|--------|--------------|
| 1 | Process New File | Pick bi-weekly Excel exports, skip/re-process duplicates, load rows into `raw_data`, copy the file into `data/`. |
| 2 | Generate Reports | Pick a month; render a compliance PDF for every supplier with data that month into `output/Report_<Month>_<Year>/<BD or CN> Region/`. |
| 3 | Generate Summary Report | Write `output/Summary_Report_<Month>_<Year>.xlsx`. |
| 4 | View Logs | Print the last 50 lines of `logs/run.log`. |
| 5 | Extract Supplier Data | One workbook per supplier for a month (same as `python -m tps.extract supplier`). |
| 6 | Import Supplier Emails | Replace the stored supplier emails with a "Supplier Name / Email" workbook. |
| 7 | Generate KPI Report | Write `output/KPI_Report_<Month>_<Year>.pdf`. |
| 8 | Clear Database | Delete all rows from `raw_data` and `supplier_emails` (schema kept), optionally reload `data/`. |

Pressing Enter at a month prompt picks the previous month
(`app.report_month_offset` in `config.yaml`).

### Extracts without the database

```bash
python -m tps.extract monthly    # output/Data_<Month>_<Year>/All_Suppliers_<Mon>_<Year>.xlsx
python -m tps.extract supplier   # output/Data_<Month>_<Year>/<BD or CN> Region/<Supplier>_<Month>_<Year>.xlsx
```

Both read the bi-weekly files in `data/` directly.

## Testing

```bash
pytest
```

The tests never touch the database or `output/`. The summary-workbook layout
tests compare against `tests/fixtures/reference_july_2026.xlsx`, which holds
real supplier data and is not in git; they skip when it is absent.

## Data & Confidentiality

This tool works on real Primark supplier and packaging-compliance data.
`.gitignore` keeps all of it out of version control: `data/`, `output/`,
`logs/`, `config.yaml` (database credentials) and `tests/fixtures/`.

## Project Docs

`docs/superpowers/specs/` and `docs/superpowers/plans/` hold the design specs
and implementation plans behind each major feature.

## License

Proprietary — internal PAC-D project built for Primark. All rights reserved.

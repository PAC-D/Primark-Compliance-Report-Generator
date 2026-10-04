# Primark Compliance Report Generator

Automated tooling for PAC-D's monthly Primark packaging-management compliance
reporting: ingest bi-weekly transaction exports, load them into a database,
and generate per-supplier compliance PDFs, an Excel summary workbook and a
KPI report, all from a local web app.

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

Everything runs from a small web app on your own PC, backed by a local
PostgreSQL database.

## Repository Structure

```
.
├── tps/                        # The application package
│   ├── __main__.py             # `python -m tps` starts the web app
│   ├── actions.py              # The app's operations (UI-free; run as background jobs)
│   ├── web/                    # Flask app: routes, job runner, page, CSS/JS
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
| Web UI        | Flask, vanilla HTML/CSS/JS (no build)   |
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

This starts the app on <http://127.0.0.1:5000> and opens it in your browser.
It only listens on this PC. Stop it with Ctrl+C in the terminal.

| Section | Action | What it does |
|---------|--------|--------------|
| Reports | Generate supplier reports | One compliance PDF per supplier with data that month, in `output/Report_<Month>_<Year>/<BD or CN> Region/`. |
| Reports | Generate summary workbook | `output/Summary_Report_<Month>_<Year>.xlsx`. |
| Reports | Generate KPI report | `output/KPI_Report_<Month>_<Year>.pdf`. |
| Reports | Extract supplier data | One workbook per supplier from the raw files in `data/` (no database). |
| Data | Load transaction files | Upload bi-weekly exports; loads them into `raw_data` and copies them into `data/`. Files already loaded are skipped unless "re-load" is ticked; re-loading replaces a file's rows, it never duplicates them. |
| Data | Import supplier emails | Replace the stored supplier emails with a "Supplier Name / Email" workbook. |
| Data | Clear database | Delete all rows from `raw_data` and `supplier_emails` (schema kept), optionally reloading `data/`. |
| — | Recent log | The last 50 lines of `logs/run.log`. |

The report month defaults to the latest month with data. Jobs run one at a
time; the page shows progress, then download links (or an "Open folder"
button for the supplier PDFs).

Regions: Bangladesh, India, Pakistan, Sri Lanka, Morocco and Turkey are BD;
every other country is CN; a supplier with countries from both is CN.

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

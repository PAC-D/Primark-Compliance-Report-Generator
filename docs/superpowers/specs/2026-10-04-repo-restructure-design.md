# Repo Restructure — Design

Date: 2026-10-04. Status: approved.

## Goal

Turn three loosely coupled folders (`tps-pipeline/`, `monthly-data-extractor/`,
`supplier-data-extractor/`) into one importable package, remove dead and
duplicated code, and keep every report byte-for-byte equivalent in content.

## Target layout

```
README.md  requirements.txt  pytest.ini  .gitignore  config.yaml.example
tps/
  __main__.py        python -m tps -> menu
  config.py          config.yaml loaded once; ROOT/DATA_DIR/OUTPUT_DIR/LOG_FILE; logging
  common.py          safe_filename, normalise_supplier, region sets + rules, month helpers, ask_report_month
  db.py              engine, sessions, schema, table clears, email inserts
  ingest.py          transaction-file ETL + supplier-email workbook import
  extract.py         monthly + per-supplier raw-data extracts (python -m tps.extract monthly|supplier)
  menu.py            UI only
  setup_db.py
  metrics/           supplier.py, summary.py, kpi.py
  reports/           html.py (jinja + logos), pdf.py, supplier_report.py, kpi_report.py, summary_excel.py
  templates/         report.html.j2, kpi_report.html.j2
  assets/
tests/               all tests; fixtures/ gitignored (confidential)
data/ output/ logs/  gitignored runtime dirs at repo root
```

All generated files land under `output/`. Extracts go to
`output/Data_<Month>_<Year>/` (combined workbook at the top, per-supplier
workbooks under `BD Region/` and `CN Region/`).

## Removed

- HTML summary report: `summary_renderer.py`, `summary_report.html.j2`,
  `get_summary_country_volume`.
- Unreferenced: `report.css`, template backup, `config/table_columns.yaml`
  and its loader, `get_volume_scores`, renderer `make_landscape_header_footer`,
  `get_renderer_config`, `calculate_corrugated_sqm`, pdfgen
  `render_and_generate_pdf`, unused `template_dir`/`page_format` branches,
  thread lock, unreachable block in `get_compliance_data`, back-compat
  aliases, `clear_raw_data`, unused imports.
- Duplicate root `monthly-data-extractor.py`, duplicate `safe_filename.py`.
- Tests that only covered removed code.

## Consolidated

- One config load, one logo loader, one Jinja environment.
- One month prompt (menu behaviour: Enter = previous month, bad input =
  default) used by menu and extract CLI.
- One "last N months" range function; one per-month series helper replacing
  four near-identical score functions.
- Supplier list SQL and email-workbook parsing move out of `menu.py`.

## Behaviour kept on purpose

- Region rules differ and stay different: menu/extract put a supplier in CN
  when *any* origin country is a CN country, else BD; KPI puts a country in BD
  only when it is a BD country, else CN. Countries in neither set therefore
  land in different regions per report. Flagged, not changed.
- Report content, filenames and menu options unchanged.

## Verification

Full test suite (`pytest` from repo root with `.venv-win`) green after each
step. Excel layout tests run against the local reference workbook.

# Repo Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One `tps/` package replacing three folders, with dead and duplicated code removed and report output unchanged.

**Architecture:** Move first (history-preserving `git mv`), then consolidate shared helpers into `tps/config.py` and `tps/common.py`, then delete dead code, then dedupe metrics/reports, then tidy the menu. Every task ends with the full suite green.

**Tech Stack:** Python 3.14, pandas, openpyxl, SQLAlchemy/PostgreSQL, Jinja2, Playwright, pypdf, pytest.

**Spec:** `docs/superpowers/specs/2026-10-04-repo-restructure-design.md`

## Global Constraints

- Test command (repo root): `.venv-win\Scripts\python.exe -m pytest -q`
- No test may write to the live database.
- Report content, output filenames and menu options stay unchanged.
- Region rules stay as they are (menu/extract: CN if any CN country; KPI: BD only if BD country).
- `tests/fixtures/` stays gitignored (real supplier data).

---

### Task 1: Move everything into `tps/` and `tests/`

**Files:**
- Move: `tps-pipeline/*.py` -> `tps/` (`database.py`->`db.py`, `processor.py`->`ingest.py`, `pdfgen.py`->`reports/pdf.py`, `renderer.py`->`reports/supplier_report.py`, `kpi_renderer.py`->`reports/kpi_report.py`, `summary_excel_renderer.py`->`reports/summary_excel.py`, `_suppliers_below.py`/`_supplier_trend.py`->`reports/`, `metrics.py`->`metrics/supplier.py`, `kpi_metrics.py`->`metrics/kpi.py`)
- Move: `tps-pipeline/templates`, `assets` -> `tps/`; `tps-pipeline/tests/*` and `supplier-data-extractor/tests/*` -> `tests/`
- Move: `config.yaml(.example)`, `requirements.txt` -> repo root; local `data/`, `output/`, `logs/` -> repo root
- Create: `tps/__init__.py`, `tps/__main__.py`, `tps/metrics/__init__.py`, `tps/reports/__init__.py`, `pytest.ini`

- [ ] `git mv` each file; plain-move the gitignored runtime dirs and config.yaml.
- [ ] Rewrite imports to absolute `tps.` paths; drop every `sys.path.insert`; update `patch("module.x")` targets.
- [ ] `pytest.ini`: `[pytest]` / `testpaths = tests` / `pythonpath = .`
- [ ] Run full suite: expect the 109 baseline tests to pass.
- [ ] Commit.

### Task 2: `tps/config.py` + `tps/common.py`

**Produces:**
- `tps.config`: `ROOT, PACKAGE_DIR, TEMPLATES_DIR, ASSETS_DIR, DATA_DIR, OUTPUT_DIR, LOG_FILE, CONFIG, REPORT_MONTH_OFFSET, setup_logging()`
- `tps.common`: `CN_REGION_COUNTRIES, BD_REGION_COUNTRIES, SUPPLIER_NORMALISATION, normalise_supplier(str)->str, safe_filename(str)->str, report_region(Iterable[str])->str, month_label(date)->str, add_months(date,int)->date, next_month_start(date)->date, months_back(date, date, count=12)->list[date], get_report_month()->date, ask_report_month(title)->date`

- [ ] Write `tests/test_common.py` (merge `test_safe_filename.py`, `test_supplier_normalisation.py`, processor's `TestNormaliseSupplier`; add `months_back`, `add_months`, `report_region` cases). Run: fails on import.
- [ ] Implement both modules; point db, metrics, renderers, menu, setup_db at them; delete `logging_config.py`, `supplier_normalisation.py`, both `safe_filename.py`.
- [ ] Full suite green. Commit.

### Task 3: `tps/extract.py`

**Produces:** `load_month_files(year, month) -> DataFrame`, `extract_monthly(year, month) -> Path`, `extract_by_supplier(year, month) -> Path`, CLI `python -m tps.extract monthly|supplier`.

- [ ] Port `tests/test_extract.py` from the supplier extractor test (paths: `tps.extract.DATA_DIR` / `OUTPUT_DIR` monkeypatched); add one monthly test. Run: fails.
- [ ] Implement; delete `monthly-data-extractor*`, `supplier-data-extractor/`. Menu option 5 calls `extract_by_supplier`.
- [ ] Full suite green. Commit.

### Task 4: Delete dead code

- [ ] Delete: `summary_renderer.py`, `summary_report.html.j2`, `report.css`, template backup, `config/`, `get_summary_country_volume`, `get_volume_scores`, renderer `make_landscape_header_footer`/`get_renderer_config`/`calculate_corrugated_sqm`/`_load_table_columns`, pdfgen `render_and_generate_pdf`/`template_dir`/`page_format` branches/lock, unreachable `get_compliance_data` tail, aliases, `clear_raw_data`, unused context keys (`month_num`, `volume_*`, `table_columns`, `enumerate`).
- [ ] Delete their tests and the two tautological "calculation" tests in test_metrics; rewrite test_renderer's nested patches as one `patch.multiple` fixture.
- [ ] Full suite green. Commit.

### Task 5: Dedupe metrics and reports

- [ ] Split `metrics/supplier.py` summary functions into `metrics/summary.py`; supplier list query (from menu) -> `metrics.supplier.get_suppliers_for_month`.
- [ ] One `_monthly_series(supplier, report_month, sql, to_score)` behind the three score functions; one `months_back` for all three chart ranges.
- [ ] `reports/html.py`: `render(template, **context)`, `PRIMARK_LOGO`, `ALLPORT_LOGO`, `DEAN_MOSS_SIGNATURE`; used by supplier/kpi reports and pdf header.
- [ ] Merge `_suppliers_below.py` and `_supplier_trend.py` into `reports/summary_excel.py`.
- [ ] Full suite green (Excel layout tests included). Commit.

### Task 6: Menu + ingest

- [ ] `ingest.import_supplier_emails(path) -> int` (raises `ValueError` with the old messages).
- [ ] Menu handlers use `ask_report_month`, `OUTPUT_DIR`, `DATA_DIR`; no SQL, no config loading.
- [ ] Full suite green. Commit.

### Task 7: Docs and cleanup

- [ ] README rewritten for the new layout; `.gitignore` paths updated; `pypdf` added to requirements; scratch files deleted.
- [ ] Smoke: `python -c "import tps.menu"`, `python -m tps.extract --help`.
- [ ] Full suite green. Commit.

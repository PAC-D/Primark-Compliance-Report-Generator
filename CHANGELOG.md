# Version History

## v2.0.0 — 2026-10-19

The terminal menu is replaced by a local web app, on top of report, rendering
and repository upgrades since v1.0.0.

### Added

- **Local web app** (`python -m tps`): month jobs (supplier reports, summary
  workbook, KPI report, extracts), transaction-file loading, supplier and
  email management, a recent log, and a progress bar with Cancel — at
  <http://127.0.0.1:5000>.
- **All Supplier Data**: every source file for a month combined into one
  workbook (the terminal's monthly extract), under
  `<month>/Supplier_Data/All_Suppliers_<Mon>_<Year>.xlsx`.
- **Supplier list**: search by name or email, filter by region and month,
  edit emails in place, and export every supplier and its emails in the
  layout Import reads.
- **Command-line extracts** (`python -m tps.extract monthly|supplier`) that
  read the bi-weekly files in `data/` directly, without the database.
- Per-month output folders under `output/` (for example
  `output/2026_August/`).

### Changed

- **Compliance and KPI reports redesigned**: one A4 document per report with
  a print header/footer (compliance transactions on landscape pages); KPI
  trends split suppliers and factories by BD/CN. Tailwind and pypdf removed.
- **Summary workbook**: new layout and table style, with KPI tiles including
  working days.
- **PDF rendering is fully offline** (Chart.js and the Inter font are
  vendored) and renders 4 reports at a time, cutting generation time.
- **Supplier email import** (a terminal-menu step in v1) is now part of the
  web app's Suppliers screens.
- **Repository restructured** into the `tps/` package (`actions`, `ingest`,
  `metrics/`, `reports/`, `web/`), with shared helpers in `tps/common.py`.
- Database loads are idempotent: already-loaded files are skipped unless
  "re-load" is ticked, and re-loading replaces a file's rows.

### Removed

- The terminal menu, `monthly-data-extractor.py` and
  `supplier-data-extractor/`, superseded by the web app and `tps.extract`.

## v1.0.0 — 2026-09-08

Initial public release. A menu-driven pipeline that ingests bi-weekly
transaction exports into PostgreSQL and generates per-supplier compliance
PDFs, summary reports and KPI reports with regional/trend charts; plus
monthly and per-supplier data extractors.

---

Compare: [`v1.0.0...v2.0.0`](https://github.com/PAC-D/Primark-Compliance-Report-Generator/compare/v1.0.0...v2.0.0)

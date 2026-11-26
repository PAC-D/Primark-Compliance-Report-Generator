# Version History

## v3.1.0 — 2026-11-21

The dashboard is rebuilt on shadcn components and the PDFs are sharper.

### Added

- **Six tabs**: Dashboard, Supplier Compliance, KPI, Reports, Data and
  Suppliers.
- **Dashboard** shows the summary workbook on screen: its five sheets, then
  the all-supplier table with bulk PDF and data downloads.
- **Supplier Compliance** shows one supplier's PDF on screen, found by
  search; with none chosen it lists the month's suppliers needing follow-up.
- Chart hover values, animated numbers (NumberFlow), GSAP page motion, and
  download progress ("Preparing…" and a toast when the file arrives).
- **New API endpoints**: `/api/dashboard` (the summary workbook's figures),
  `/api/supplier` (one supplier's report figures),
  `/api/supplier-transactions` (its lines, paged and searchable) and
  `/api/search` (supplier and factory names with lines in a month).

### Changed

- **Restyled with shadcn** (buttons, dialogs, tables, selects, toasts) in
  light and dark; the clear-database confirm is now a dialog.
- **PDF charts render at 3x pixel density** for sharper print and zoom.
- Logos sit without a box behind them.
- A change that rounds to zero shows no sign (not "−0.0").
- Invalid request values (a bad month, for example) now return 400 with
  `{"error": ...}`; they were 422.

### Removed

- The v1 table, field, card, meter and chart components.

## v3.0.0 — 2026-11-20

The local Flask app is replaced by a web dashboard on the Lightsail server.

### Added

- **Dashboard** (Next.js, under `/compliance`): Supplier Compliance, KPI
  Dashboard, Reports, Data and Suppliers pages.
- **FastAPI back end** over the `tps` package, with background jobs,
  cross-site POST protection and an `ALLOWED_ORIGINS` setting.
- **Docker Compose deployment**: `api` and `web` containers, an nginx config
  with basic auth, and `deploy/release.sh`.

### Changed

- Database settings come from `DB_*` environment variables (`config.yaml`
  remains for local use); `PDF_WORKERS` is configurable (default 2).

### Removed

- The Flask app (`python -m tps`) and `tps/setup_db.py`.

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

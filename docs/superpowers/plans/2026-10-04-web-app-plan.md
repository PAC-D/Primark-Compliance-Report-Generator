# Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Local Flask web app replacing the terminal menu.

**Architecture:** UI-free operations in `tps/actions.py`; `tps/web/jobs.py` runs one at a time on a background thread; `tps/web/app.py` exposes them to a single Jinja page with a little JS polling `/job`.

**Tech Stack:** Flask 3, Jinja2, vanilla JS/CSS; existing tps package.

**Spec:** `docs/superpowers/specs/2026-10-04-web-app-design.md`

## Global Constraints

- Bind `127.0.0.1` only. No new dependency beyond `flask>=3.0`.
- Tests never touch the live DB or `output/`.
- Report content and output file names unchanged.

---

### Task 1: `tps/actions.py`

**Produces:** `Result(summary: str, files: list[Path] = [], folder: Path | None = None, details: list[str] = [])`;
`latest_data_month() -> date`; `load_transaction_files(paths, reprocess=False, progress=None) -> Result`;
`clear_database(reload: bool, progress=None) -> Result`; `generate_supplier_reports(month, progress=None) -> Result`;
`generate_summary_report(month, progress=None) -> Result`; `generate_kpi_report(month, progress=None) -> Result`;
`extract_supplier_data(month, progress=None) -> Result`; `import_emails(path, progress=None) -> Result`; `tail_log(lines=50) -> list[str]`.

- [ ] `tests/test_actions.py` (port test_menu cases + skip/reprocess, supplier-report skips). Fails on import.
- [ ] Implement; suite green; commit.

### Task 2: `tps/web/jobs.py` + `tps/web/app.py`

**Produces:** `JobRunner(inline=False).submit(name, fn, *args, **kwargs) -> Job` (raises `Busy`), `.current`;
`create_app(runner=None) -> Flask` with `GET /`, `GET /job`, `POST /jobs/<action>`, `GET /logs`, `GET /output/<path>`, `POST /open-folder`.

- [ ] `tests/test_web.py`: index renders default month; KPI job result links; busy -> 409; upload keeps names; output path traversal -> 404.
- [ ] Implement routes; suite green; commit.

### Task 3: Page + entry point

- [ ] `index.html`, `app.js`, `app.css`; `python -m tps` starts server + opens browser; delete `menu.py` and `test_menu.py`; README + requirements.
- [ ] Manual smoke in the browser (summary + KPI for Aug 2026); suite green; commit.

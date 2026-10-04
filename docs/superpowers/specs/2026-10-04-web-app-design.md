# Web App — Design

Date: 2026-10-04. Status: approved.

## Goal

Replace the terminal menu with a local web app offering the same eight
actions, with progress for long jobs and download links for outputs.

## Decisions

- Local only: Flask dev server bound to `127.0.0.1:5000`; no login.
  Team use later = change host + add login; nothing else changes.
- Same eight actions as the menu; `tps/menu.py` is deleted.
  `python -m tps.extract` stays as a CLI.
- Flask + server-rendered Jinja page + small vanilla JS (no build step).

## Structure

```
tps/actions.py        the eight operations, UI-free; long ones take progress(done, total, message)
tps/web/app.py        Flask routes, create_app(runner)
tps/web/jobs.py       JobRunner: one job at a time on a background thread, status in memory
tps/web/templates/index.html, tps/web/static/app.js, app.css
tps/__main__.py       python -m tps -> start server, open browser
```

## Behaviour

- One page, three groups: Data (upload transaction files with a
  "re-process already-loaded files" checkbox, import supplier emails, clear
  database with confirm + optional reload), Reports (supplier PDFs, summary
  workbook, KPI report), Tools (supplier data extract, log viewer).
- Month pickers are `<input type="month">`, defaulting to the latest month
  with data (fallback: the config default month).
- Jobs run one at a time; a second submission while busy is refused (HTTP
  409) and buttons are disabled. Progress shows `done/total` and a message.
- Results: download links for files under `output/`; supplier PDFs get an
  "open folder" button (local Windows only).
- Uploads keep their original file names (duplicate check and month
  extracts rely on them).
- PDF jobs close the Playwright browser in their own thread when done
  (Playwright's sync API is thread-bound).

## Verification

`tests/test_actions.py` replaces the menu tests (mocks, no live DB, temp
output dir). `tests/test_web.py` drives routes with Flask's test client and
an inline job runner. Manual smoke: run the app, generate a summary and a
KPI report for August 2026 in the browser.

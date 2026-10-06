"""The pipeline's user-facing operations, free of any UI.

The web app runs these as background jobs. Long operations report through
progress(done, total, message); every operation returns a Result.
"""

import logging
import queue
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook

from tps import config
from tps.common import get_report_month, report_region, safe_filename, split_emails
from tps.db import clear_raw_data, set_supplier_emails
from tps.extract import extract_by_supplier, extract_monthly, monthly_path
from tps.ingest import copy_to_data, import_supplier_emails, is_file_processed, process_file
from tps.metrics.summary import get_latest_data_month, get_summary_sources, get_supplier_emails_map
from tps.metrics.supplier import get_supplier_countries_by_month, get_supplier_kpis, get_suppliers_for_month
from tps.reports.kpi_report import render_kpi_report
from tps.reports.pdf import close_browser, html_to_pdf
from tps.reports.summary_excel import render_summary_excel
from tps.reports.supplier_report import render_report

logger = logging.getLogger(__name__)

# ponytail: 4 render threads, each driving its own headless Chromium (~200 MB).
# Chromium does the heavy lifting in its own processes, so threads parallelise fine;
# raise on a machine with more cores and memory, lower if it struggles.
PDF_WORKERS = 4


@dataclass
class Result:
    summary: str
    files: list[Path] = field(default_factory=list)
    folder: Path | None = None
    details: list[str] = field(default_factory=list)


def _no_progress(done: int, total: int, message: str) -> None:
    pass


def summary_path(report_month: date) -> Path:
    return config.month_folder(report_month) / f"Summary_Report_{report_month:%B_%Y}.xlsx"


def kpi_path(report_month: date) -> Path:
    return config.month_folder(report_month) / f"KPI_Report_{report_month:%B_%Y}.pdf"


def latest_data_month() -> date:
    """Most recent month with handover data; the config default when the DB is empty."""
    return get_latest_data_month() or get_report_month()


def month_status(report_month: date) -> dict:
    """What exists for a month: data in the DB, and which outputs are on disk."""
    folder = config.month_folder(report_month)

    def stamp(paths, **extra):
        paths = list(paths)
        if not paths:
            return None
        newest = max(p.stat().st_mtime for p in paths)
        return {"count": len(paths), "updated": datetime.fromtimestamp(newest).isoformat(), **extra}

    reports = folder / config.SUPPLIER_REPORTS
    data = folder / config.SUPPLIER_DATA
    summary, kpi = summary_path(report_month), kpi_path(report_month)
    combined = monthly_path(report_month.year, report_month.month)
    return {
        **get_summary_sources(report_month),
        "outputs": {
            "supplier-reports": stamp(reports.glob("*/*.pdf"), folder=reports),
            "summary": stamp([summary] if summary.exists() else [], file=summary),
            "kpi": stamp([kpi] if kpi.exists() else [], file=kpi),
            "extract": stamp(data.glob("*/*.xlsx"), folder=data),
            "all-supplier-data": stamp([combined] if combined.exists() else [], file=combined),
        },
    }


def load_transaction_files(paths, reprocess: bool = False, copy: bool = True,
                           progress=_no_progress) -> Result:
    """Load bi-weekly exports into raw_data. Files already loaded are skipped
    unless reprocess is set; loading a file again replaces its rows."""
    loaded, details = 0, []
    for i, path in enumerate(paths):
        name = Path(path).name
        progress(i, len(paths), f"Loading {name}")
        logger.info(f"Processing file: {path}")
        if not reprocess and is_file_processed(path):
            logger.info("File already processed, skipping")
            details.append(f"Already loaded, skipped: {name}")
            continue
        try:
            rows = process_file(str(path))
            if copy:
                copy_to_data(path)
            logger.info(f"Inserted {rows} rows from {name}")
            details.append(f"Loaded {name} ({rows} rows)")
            loaded += 1
        except Exception as e:
            logger.warning(f"Error processing file {name}: {e}")
            details.append(f"Failed {name}: {e}")
    return Result(f"Loaded {loaded} of {len(paths)} file(s)", details=details)


def clear_database(reload: bool = False, progress=_no_progress) -> Result:
    """Delete every row from raw_data (supplier emails are kept); optionally reload data/."""
    clear_raw_data()
    logger.info("Database cleared: all rows removed from raw_data")
    if not reload:
        return Result("Database cleared (supplier emails kept)")

    files = sorted(config.DATA_DIR.glob("*.xlsx")) + sorted(config.DATA_DIR.glob("*.xls"))
    loaded = load_transaction_files(files, reprocess=True, copy=False, progress=progress)
    return Result(f"Database cleared, then {loaded.summary.lower()}", details=loaded.details)


def _supplier_pdf(supplier: str, report_month: date, folder: Path) -> Path:
    """One supplier's compliance PDF. Runs on a render thread with its own browser."""
    origin_country = get_supplier_kpis(supplier, report_month).get("origin_country", "")
    region_folder = folder / report_region(origin_country.split(","))
    region_folder.mkdir(parents=True, exist_ok=True)
    output_path = region_folder / f"{safe_filename(supplier)}_{report_month:%B_%Y}.pdf"

    html = render_report(supplier, report_month)
    # Drop the old copy first so a failed run never leaves a stale report behind.
    output_path.unlink(missing_ok=True)
    html_to_pdf(html, str(output_path), header_footer=True)
    return output_path


def generate_supplier_reports(report_month: date, progress=_no_progress) -> Result:
    """One compliance PDF per supplier with data in the month, rendered
    PDF_WORKERS at a time, under <month>/Supplier_Reports/<BD or CN>_Region/."""
    suppliers = get_suppliers_for_month(report_month)
    if not suppliers:
        return Result(f"No suppliers with data in {report_month:%B %Y}")

    folder = config.month_folder(report_month) / config.SUPPLIER_REPORTS
    logger.info(f"Starting report generation for {len(suppliers)} suppliers")
    todo, finished, stop = queue.SimpleQueue(), queue.SimpleQueue(), threading.Event()
    for supplier in suppliers:
        todo.put(supplier)

    def worker():
        # Each thread has its own browser (pdf.py), closed here in the same thread.
        try:
            while not stop.is_set():
                try:
                    supplier = todo.get_nowait()
                except queue.Empty:
                    return
                try:
                    finished.put((supplier, _supplier_pdf(supplier, report_month, folder), None))
                except Exception as e:
                    finished.put((supplier, None, e))
        finally:
            close_browser()

    workers = [threading.Thread(target=worker, daemon=True) for _ in range(min(PDF_WORKERS, len(suppliers)))]
    for w in workers:
        w.start()
    generated, details = 0, []
    progress(0, len(suppliers), "Starting renderers")
    try:
        for done in range(1, len(suppliers) + 1):
            supplier, path, error = finished.get()
            if error is None:
                logger.info(f"Report saved: {path}")
                generated += 1
            else:
                logger.error(f"Error generating report for {supplier}: {error}")
                details.append(f"Skipped {supplier}: {error}")
            progress(done, len(suppliers), supplier)  # raises if cancelled
    finally:
        stop.set()  # on cancel: workers finish their current supplier, then stop
        for w in workers:
            w.join()

    summary = f"Generated {generated} reports, {len(details)} skipped"
    logger.info(summary)
    return Result(summary, folder=folder, details=details)


def generate_summary_report(report_month: date, progress=_no_progress) -> Result:
    progress(0, 1, "Building the workbook")
    wb = render_summary_excel(report_month)
    path = summary_path(report_month)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    logger.info(f"Summary report saved: {path}")
    return Result(f"Summary workbook for {report_month:%B %Y}", files=[path])


def generate_kpi_report(report_month: date, progress=_no_progress) -> Result:
    """Raises ValueError when the month has no data."""
    progress(0, 1, "Rendering the PDF")
    html = render_kpi_report(report_month)
    path = kpi_path(report_month)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    try:
        html_to_pdf(html, str(path), header_footer=True)
    finally:
        # Playwright's sync API is bound to the thread that started it.
        close_browser()
    logger.info(f"KPI report saved: {path}")
    return Result(f"KPI report for {report_month:%B %Y}", files=[path])


def extract_supplier_data(report_month: date, progress=_no_progress) -> Result:
    progress(0, 1, "Writing one workbook per supplier")
    folder = extract_by_supplier(report_month.year, report_month.month)
    return Result(f"Supplier data for {report_month:%B %Y}", folder=folder)


def extract_all_supplier_data(report_month: date, progress=_no_progress) -> Result:
    """Raises FileNotFoundError when data/ has no files for the month."""
    progress(0, 1, "Combining the month's files from data/")
    path = extract_monthly(report_month.year, report_month.month)
    return Result(f"All supplier data for {report_month:%B %Y}", files=[path])


def import_emails(path, progress=_no_progress) -> Result:
    count = import_supplier_emails(path)
    logger.info(f"Imported emails for {count} suppliers")
    return Result(f"Updated emails for {count} suppliers")


def supplier_list() -> list[dict]:
    """Every supplier with transaction data or stored emails, by name: its emails,
    and its region overall and in each month with data ('YYYY-MM' -> region).
    Emails are matched case-insensitively; email-only suppliers have no region."""
    emails = get_supplier_emails_map()
    by_supplier: dict[str, dict[str | None, list[str]]] = {}
    for supplier, month, countries in get_supplier_countries_by_month():
        by_supplier.setdefault(supplier, {})[month] = countries

    suppliers = [{
        "name": name,
        "emails": emails.get(name.strip().lower(), ""),
        "region": report_region(c for countries in months.values() for c in countries),
        "months": {m: report_region(countries) for m, countries in sorted(months.items()) if m},
    } for name, months in by_supplier.items()]
    known = {name.strip().lower() for name in by_supplier}
    suppliers += [{"name": name, "emails": value, "region": None, "months": {}}
                  for name, value in emails.items() if name not in known]
    return sorted(suppliers, key=lambda s: s["name"].lower())


def save_supplier_emails(supplier: str, emails: str) -> str:
    """Replace one supplier's emails; blank removes them. Returns the stored list."""
    addresses = split_emails(emails)
    set_supplier_emails({supplier: addresses})
    logger.info(f"Saved {len(addresses)} email(s) for {supplier}")
    return ", ".join(addresses)


def supplier_emails_workbook() -> Workbook:
    """Every supplier and its emails, in the layout import_supplier_emails reads."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Supplier Emails"
    ws.append(["Supplier Name", "Email"])
    for supplier in supplier_list():
        ws.append([supplier["name"], supplier["emails"]])
    ws.column_dimensions["A"].width = 60
    ws.column_dimensions["B"].width = 80
    return wb


def tail_log(lines: int = 50) -> list[str]:
    try:
        return config.LOG_FILE.read_text(errors="replace").splitlines()[-lines:]
    except FileNotFoundError:
        return []

"""Text menu - the entry point for every pipeline task (python -m tps)."""

import logging
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from tps.common import ask_report_month, report_region, safe_filename
from tps.config import DATA_DIR, LOG_FILE, OUTPUT_DIR, setup_logging
from tps.db import clear_all_tables
from tps.extract import extract_by_supplier
from tps.ingest import copy_to_data, import_supplier_emails, is_file_processed, process_file
from tps.metrics.supplier import get_supplier_kpis, get_suppliers_for_month
from tps.reports.kpi_report import render_kpi_report
from tps.reports.pdf import html_to_pdf, html_to_pdf_mixed
from tps.reports.summary_excel import render_summary_excel
from tps.reports.supplier_report import render_report

setup_logging()
logger = logging.getLogger(__name__)

MAX_LOG_LINES = 50
EXCEL_FILETYPES = [("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]


def print_banner():
    banner = """
============================================
   TPS Compliance Report Generator
============================================
   [1] Process New File
   [2] Generate Reports
   [3] Generate Summary Report
   [4] View Logs
   [5] Extract Supplier Data
   [6] Import Supplier Emails
   [7] Generate KPI Report
   [8] Clear Database
   [0] Exit
============================================
    """
    print(banner)


def _pick_excel(title: str, multiple: bool = False):
    """Native file dialog; returns a path, a tuple of paths, or '' when cancelled."""
    root = tk.Tk()
    root.withdraw()
    try:
        ask = filedialog.askopenfilenames if multiple else filedialog.askopenfilename
        return ask(title=title, filetypes=EXCEL_FILETYPES)
    finally:
        root.destroy()


def _load_file(filepath, copy: bool) -> None:
    """Insert one file into raw_data; a failure is reported and skipped."""
    filename = Path(filepath).name
    try:
        row_count = process_file(str(filepath))
        if copy:
            copy_to_data(filepath)
        logger.info(f"Inserted {row_count} rows from {filename}")
        print(f"Successfully processed: {filename} ({row_count} rows)")
    except Exception as e:
        logger.warning(f"Error processing file {filename}: {e}")
        print(f"Warning: {filename} failed - {e}. Skipping.")


def handle_process_file():
    for filepath in _pick_excel("Select Transaction Data Excel File(s)", multiple=True):
        logger.info(f"Processing file: {filepath}")
        if is_file_processed(filepath):
            filename = Path(filepath).name
            logger.info("File already processed, skipping")
            print(f"File already processed: {filename}")
            if input(f"Re-process {filename}? (y/n): ").strip().lower() != "y":
                continue
        _load_file(filepath, copy=True)


def handle_reload_data():
    filepaths = sorted(DATA_DIR.glob("*.xlsx")) + sorted(DATA_DIR.glob("*.xls"))
    if not filepaths:
        print("No files found in data/ folder.")
        return
    for filepath in filepaths:
        logger.info(f"Reloading file: {filepath}")
        _load_file(filepath, copy=False)


def handle_generate_reports():
    report_month = ask_report_month("Report Month Selection")

    suppliers = get_suppliers_for_month(report_month)
    if not suppliers:
        print("No suppliers found in database.")
        return

    file_date = report_month.strftime("%B_%Y")
    logger.info(f"Starting report generation for {len(suppliers)} suppliers")
    success_count = 0
    skip_count = 0

    for i, supplier in enumerate(suppliers, 1):
        logger.info(f"Generating report {i}/{len(suppliers)} for: {supplier}")
        print(f"Generating report {i}/{len(suppliers)} for: {supplier}...")
        try:
            origin_country = get_supplier_kpis(supplier, report_month).get("origin_country", "")
            region_folder = OUTPUT_DIR / f"Report_{file_date}" / report_region(origin_country.split(","))
            region_folder.mkdir(parents=True, exist_ok=True)
            output_path = region_folder / f"{safe_filename(supplier)}_{file_date}.pdf"

            portrait_html, landscape_html = render_report(supplier, report_month)
            # Drop the old copy first so a failed run never leaves a stale report behind.
            output_path.unlink(missing_ok=True)
            html_to_pdf_mixed(portrait_html, landscape_html, str(output_path))
            logger.info(f"Report saved: {output_path}")
            success_count += 1
        except Exception as e:
            logger.error(f"Error generating report for {supplier}: {e}")
            print(f"  Skipped: {supplier} - {e}")
            skip_count += 1

    logger.info(f"Generated {success_count} reports, {skip_count} skipped")
    print(f"Generated {success_count} reports, {skip_count} skipped.")


def handle_generate_summary_report():
    report_month = ask_report_month("Summary Report Month Selection")
    print("Rendering summary report...")
    try:
        wb = render_summary_excel(report_month)
        OUTPUT_DIR.mkdir(exist_ok=True)
        output_path = OUTPUT_DIR / f"Summary_Report_{report_month.strftime('%B_%Y')}.xlsx"
        wb.save(str(output_path))
        logger.info(f"Summary report saved: {output_path}")
        print(f"Summary report generated: {output_path}")
    except Exception as e:
        logger.error(f"Error generating summary report: {e}")
        print(f"Error generating summary report: {e}")


def handle_generate_kpi_report():
    report_month = ask_report_month("KPI Report Month Selection")
    print("Rendering KPI report...")
    try:
        html = render_kpi_report(report_month)
        OUTPUT_DIR.mkdir(exist_ok=True)
        output_path = OUTPUT_DIR / f"KPI_Report_{report_month.strftime('%B_%Y')}.pdf"
        output_path.unlink(missing_ok=True)
        html_to_pdf(html, str(output_path))
        logger.info(f"KPI report saved: {output_path}")
        print(f"KPI report generated: {output_path}")
    except ValueError as e:
        logger.warning(f"KPI report skipped: {e}")
        print(f"KPI report skipped: {e}")
    except Exception as e:
        logger.error(f"Error generating KPI report: {e}")
        print(f"Error generating KPI report: {e}")


def handle_view_logs():
    try:
        lines = LOG_FILE.read_text().splitlines()
    except FileNotFoundError:
        print("No logs found yet.")
        return
    except Exception as e:
        print(f"Error reading logs: {e}")
        return
    for line in lines[-MAX_LOG_LINES:]:
        print(line)


def handle_extract_supplier_data():
    try:
        report_month = ask_report_month("Supplier Data Extraction Month Selection")
        extract_by_supplier(report_month.year, report_month.month)
    except Exception as e:
        logger.error(f"Error extracting supplier data: {e}")
        print(f"Error: {e}")


def handle_import_emails():
    filepath = _pick_excel("Select Supplier Emails Excel File")
    if not filepath:
        return

    logger.info(f"Importing supplier emails from: {filepath}")
    try:
        count = import_supplier_emails(filepath)
    except ValueError as e:
        print(f"Error: {e}")
        return
    except Exception as e:
        logger.error(f"Error importing supplier emails: {e}")
        print(f"Error importing supplier emails: {e}")
        return
    logger.info(f"Imported {count} supplier emails")
    print(f"Successfully imported {count} supplier emails")


def handle_clear_database():
    print("\n=== Clear Database ===")
    response = input("This will DELETE ALL rows from raw_data and supplier_emails (tables are kept). Continue? (y/n): ").strip().lower()
    if response != "y":
        print("Canceled.")
        return
    try:
        clear_all_tables()
        logger.info("Database cleared: all rows removed from raw_data and supplier_emails")
        print("Database cleared: all rows removed. Tables preserved.")
    except Exception as e:
        logger.error(f"Error clearing database: {e}")
        print(f"Error clearing database: {e}")
        return

    if input("Reload data from the data/ folder? (y/n): ").strip().lower() == "y":
        handle_reload_data()


ACTIONS = {
    "1": handle_process_file,
    "2": handle_generate_reports,
    "3": handle_generate_summary_report,
    "4": handle_view_logs,
    "5": handle_extract_supplier_data,
    "6": handle_import_emails,
    "7": handle_generate_kpi_report,
    "8": handle_clear_database,
}


def main():
    print_banner()
    while True:
        choice = input("\nSelect option: ").strip()
        if choice == "0":
            print("Goodbye!")
            break
        action = ACTIONS.get(choice)
        if action:
            action()
        else:
            print("Invalid option. Try again.")


if __name__ == "__main__":
    main()

"""All routes, under /api."""

import shutil
import tempfile
import threading
from datetime import date
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from tps import actions, config
from tps.common import json_safe, safe_filename
from tps.extract import supplier_data_zip, supplier_workbook
from tps.jobs import Busy, Job, JobRunner
from tps.metrics.dashboard import Filters, filter_options, kpi, search, supplier_compliance
from tps.metrics.supplier import get_transactions_page
from tps.reports.pdf import close_browser
from tps.reports.summary_excel import summary_context
from tps.reports.supplier_report import report_context

# Month-based jobs: URL name -> (label, actions function name).
MONTH_JOBS = {
    "supplier-reports": ("Supplier Reports", "generate_supplier_reports"),
    "summary": ("Summary Workbook", "generate_summary_report"),
    "kpi": ("KPI Report", "generate_kpi_report"),
    "extract": ("Supplier Data", "extract_supplier_data"),
    "all-supplier-data": ("All Supplier Data", "extract_all_supplier_data"),
}
EXCEL_SUFFIXES = {".xlsx", ".xls"}
# ponytail: one on-demand Chromium at a time; a queue only if clicks pile up
_pdf_lock = threading.Lock()
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _month(value: str) -> date:
    try:
        return date.fromisoformat(value + "-01")
    except ValueError:
        raise HTTPException(400, "Month must look like 2026-08.")


def _output_relative(path: Path) -> str:
    return Path(path).resolve().relative_to(config.OUTPUT_DIR.resolve()).as_posix()


def _job_json(job: Job | None) -> dict | None:
    if job is None:
        return None
    result = job.result
    return {
        "id": job.id, "name": job.name, "state": job.state,
        "done": job.done, "total": job.total, "message": job.message, "error": job.error,
        "cancelling": job.cancel_requested,
        "result": result and {
            "summary": result.summary,
            "details": result.details,
            "files": [_output_relative(p) for p in result.files],
            "folder": result.folder and _output_relative(result.folder),
        },
    }


def _save_uploads(files: list[UploadFile]) -> tuple[Path, list[Path]]:
    """Save Excel uploads under their original names - the duplicate check and
    the month extracts rely on them - in a fresh temp folder."""
    folder = Path(tempfile.mkdtemp(prefix="tps-upload-"))
    paths = []
    for upload in files:
        name = safe_filename(Path((upload.filename or "").replace("\\", "/")).name)
        if Path(name).suffix.lower() in EXCEL_SUFFIXES:
            with open(folder / name, "wb") as out:
                shutil.copyfileobj(upload.file, out)
            paths.append(folder / name)
    return folder, paths


def _removing(folder: Path, fn):
    """fn, followed by deleting the upload folder however it ends."""
    def run(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        finally:
            shutil.rmtree(folder, ignore_errors=True)
    return run


def _attachment(content: bytes, name: str, media_type: str, inline: bool = False) -> Response:
    """A download (or, inline, a file the browser shows in the tab), named `name`."""
    kind = "inline" if inline else "attachment"
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": f"{kind}; filename*=UTF-8''{quote(name)}"})


def _filters(month, region, country, supplier, factory, approved_by) -> Filters:
    def clean(v):
        return None if v in (None, "", "all") else v
    return Filters(_month(month), (clean(region) or "").upper() or None, clean(country), clean(supplier),
                   clean(factory), clean(approved_by))


def make_router(runner: JobRunner) -> APIRouter:
    router = APIRouter(prefix="/api")

    def start(name, fn, *args, upload_folder: Path | None = None, **kwargs):
        if upload_folder:
            fn = _removing(upload_folder, fn)
        try:
            job = runner.submit(name, fn, *args, **kwargs)
        except Busy as busy:
            if upload_folder:
                shutil.rmtree(upload_folder, ignore_errors=True)
            return JSONResponse(
                {"error": f"{busy} is still running. Wait for it to finish, or cancel it."}, status_code=409)
        return _job_json(job)

    @router.get("/health")
    def health():
        return {"ok": True}

    @router.get("/latest-month")
    def latest_month():
        return {"month": f"{actions.latest_data_month():%Y-%m}"}

    @router.get("/supplier-compliance")
    def compliance(month: str, region: str | None = None, country: str | None = None,
                   supplier: str | None = None, factory: str | None = None, approved_by: str | None = None):
        return supplier_compliance(_filters(month, region, country, supplier, factory, approved_by))

    @router.get("/kpi")
    def kpi_data(month: str, region: str | None = None, country: str | None = None,
                 supplier: str | None = None, factory: str | None = None, approved_by: str | None = None):
        return kpi(_filters(month, region, country, supplier, factory, approved_by))

    @router.get("/dashboard")
    def dashboard(month: str):
        context = summary_context(_month(month))
        # only the Follow-Up emails go out, not every supplier's
        wanted = {s["supplier"].strip().lower() for s in context["suppliers_below"]}
        context["email_map"] = {k: v for k, v in context["email_map"].items() if k in wanted}
        return json_safe(context)

    @router.get("/supplier")
    def supplier_page(supplier: str, month: str):
        report_month = _month(month)
        context = report_context(supplier, report_month, transactions=False)
        if context["kpis"]["total_lines"] == 0:
            raise HTTPException(404, f"No lines for this supplier in {report_month:%B %Y}.")
        return json_safe(context)

    @router.get("/supplier-transactions")
    def supplier_transactions(supplier: str, month: str, q: str | None = None, page: int = 1):
        size = 50
        rows, total = get_transactions_page(supplier, _month(month), q, page, size)
        page = max(1, min(page, -(-total // size) or 1))
        return json_safe({"rows": rows, "total": total, "page": page, "page_size": size})

    @router.get("/search")
    def search_names(month: str, q: str = ""):
        return search(_month(month), q)

    @router.get("/month-status")
    def month_status(month: str):
        status = actions.month_status(_month(month))
        for item in status["outputs"].values():
            for key in ("folder", "file"):
                if item and key in item:
                    item[key] = _output_relative(item[key])
        return status

    @router.get("/supplier-pdf")
    def supplier_pdf(supplier: str, month: str, inline: bool = False):
        report_month = _month(month)
        folder = Path(tempfile.mkdtemp(prefix="tps-pdf-"))
        try:
            with _pdf_lock:
                try:
                    pdf = actions._supplier_pdf(supplier, report_month, folder)
                finally:
                    close_browser()  # Playwright is bound to this thread
                content = pdf.read_bytes()
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        return _attachment(content, f"{safe_filename(supplier)}_{report_month:%B_%Y}.pdf", "application/pdf",
                           inline=inline)

    @router.get("/supplier-data")
    def supplier_data(supplier: str, month: str):
        report_month = _month(month)
        return _attachment(supplier_workbook(supplier, report_month),
                           f"{safe_filename(supplier)}_{report_month:%B_%Y}.xlsx", XLSX)

    @router.get("/supplier-data-zip")
    def supplier_data_archive(month: str, supplier: list[str] = Query(default=[])):
        report_month = _month(month)
        content = supplier_data_zip(supplier, report_month)
        if content is None:
            raise HTTPException(404, f"None of these suppliers has data in {report_month:%B %Y}.")
        return _attachment(content, f"Supplier_Data_{report_month:%B_%Y}.zip", "application/zip")

    @router.get("/options")
    def options(month: str):
        return filter_options(_month(month))

    @router.get("/job")
    def current_job():
        return _job_json(runner.current)

    @router.post("/job/cancel")
    def cancel_job():
        runner.cancel()
        return _job_json(runner.current)

    @router.post("/jobs/{kind}")
    def month_job(kind: str, month: str = Form(), supplier: list[str] = Form(default=[])):
        if kind not in MONTH_JOBS:
            raise HTTPException(404, "Unknown job")
        label, fn_name = MONTH_JOBS[kind]
        report_month = _month(month)
        args = (report_month, supplier or None) if kind == "supplier-reports" else (report_month,)
        return start(f"{label} · {report_month:%B %Y}", getattr(actions, fn_name), *args)

    @router.post("/upload")
    def upload(files: list[UploadFile] = [], reprocess: str | None = Form(default=None)):
        folder, paths = _save_uploads(files)
        if not paths:
            shutil.rmtree(folder, ignore_errors=True)
            raise HTTPException(400, "Choose at least one Excel file (.xlsx).")
        return start("Load Transaction Files", actions.load_transaction_files, paths,
                     reprocess=reprocess is not None, upload_folder=folder)

    @router.post("/clear")
    def clear():
        return start("Clear Database", actions.clear_database)

    @router.get("/suppliers")
    def suppliers():
        return actions.supplier_list()

    @router.post("/suppliers/emails")
    def save_supplier_emails(supplier: str = Form(), emails: str = Form(default="")):
        return {"emails": actions.save_supplier_emails(supplier, emails)}

    @router.post("/suppliers/import")
    def import_emails(file: UploadFile | None = None):
        folder, paths = _save_uploads([file] if file else [])
        if not paths:
            shutil.rmtree(folder, ignore_errors=True)
            raise HTTPException(400, "Choose an Excel file (.xlsx).")
        return start("Import Supplier Emails", actions.import_emails, paths[0], upload_folder=folder)

    @router.get("/suppliers/export")
    def export_supplier_emails():
        buffer = BytesIO()
        actions.supplier_emails_workbook().save(buffer)
        return _attachment(buffer.getvalue(), f"Supplier_Emails_{date.today():%Y-%m-%d}.xlsx", XLSX)

    @router.get("/logs")
    def logs():
        return {"lines": actions.tail_log()}

    @router.get("/output/{path:path}")
    def output_file(path: str):
        root = config.OUTPUT_DIR.resolve()
        target = (root / path).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise HTTPException(404, "Not found")
        return FileResponse(target, filename=target.name)

    return router

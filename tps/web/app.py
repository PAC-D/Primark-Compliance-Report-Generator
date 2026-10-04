"""Local web UI: one page, the pipeline's actions run as background jobs."""

import os
import shutil
import tempfile
from datetime import date
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_from_directory

from tps import actions, config
from tps.common import safe_filename
from tps.web.jobs import Busy, Job, JobRunner

# Month-based jobs: URL name -> (label, actions function name).
MONTH_JOBS = {
    "supplier-reports": ("Supplier Reports", "generate_supplier_reports"),
    "summary": ("Summary Workbook", "generate_summary_report"),
    "kpi": ("KPI Report", "generate_kpi_report"),
    "extract": ("Supplier Data", "extract_supplier_data"),
}
EXCEL_SUFFIXES = {".xlsx", ".xls"}


def _month(value: str) -> date:
    """<input type="month"> and the URLs use YYYY-MM."""
    return date.fromisoformat(value + "-01")


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


def _save_uploads(files) -> tuple[Path, list[Path]]:
    """Save Excel uploads under their original names - the duplicate check and
    the month extracts rely on them - in a fresh temp folder."""
    folder = Path(tempfile.mkdtemp(prefix="tps-upload-"))
    paths = []
    for upload in files:
        name = safe_filename(Path(upload.filename or "").name)
        if Path(name).suffix.lower() in EXCEL_SUFFIXES:
            upload.save(folder / name)
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


def create_app(runner: JobRunner | None = None) -> Flask:
    app = Flask(__name__)
    runner = runner or JobRunner()

    def start(name, fn, *args, upload_folder: Path | None = None, **kwargs):
        if upload_folder:
            fn = _removing(upload_folder, fn)
        try:
            job = runner.submit(name, fn, *args, **kwargs)
        except Busy as busy:
            if upload_folder:
                shutil.rmtree(upload_folder, ignore_errors=True)
            return jsonify(error=f"{busy} is still running. Wait for it to finish, or cancel it."), 409
        return jsonify(_job_json(job))

    @app.get("/")
    def index():
        return render_template("index.html", month=f"{actions.latest_data_month():%Y-%m}",
                               job=_job_json(runner.current))

    @app.get("/month/<value>")
    def month_status(value):
        status = actions.month_status(_month(value))
        for item in status["outputs"].values():
            for key in ("folder", "file"):
                if item and key in item:
                    item[key] = _output_relative(item[key])
        return jsonify(status)

    @app.get("/job")
    def current_job():
        return jsonify(_job_json(runner.current))

    @app.post("/job/cancel")
    def cancel_job():
        runner.cancel()
        return jsonify(_job_json(runner.current))

    @app.post("/jobs/<kind>")
    def month_job(kind):
        if kind not in MONTH_JOBS:
            abort(404)
        label, fn_name = MONTH_JOBS[kind]
        report_month = _month(request.form["month"])
        return start(f"{label} · {report_month:%B %Y}", getattr(actions, fn_name), report_month)

    @app.post("/jobs/upload")
    def upload():
        folder, paths = _save_uploads(request.files.getlist("files"))
        if not paths:
            shutil.rmtree(folder, ignore_errors=True)
            return jsonify(error="Choose at least one Excel file (.xlsx)."), 400
        return start("Load Transaction Files", actions.load_transaction_files, paths,
                     reprocess="reprocess" in request.form, upload_folder=folder)

    @app.post("/jobs/emails")
    def emails():
        folder, paths = _save_uploads(request.files.getlist("file"))
        if not paths:
            shutil.rmtree(folder, ignore_errors=True)
            return jsonify(error="Choose an Excel file (.xlsx)."), 400
        return start("Import Supplier Emails", actions.import_emails, paths[0], upload_folder=folder)

    @app.post("/jobs/clear")
    def clear():
        return start("Clear Database", actions.clear_database, reload="reload" in request.form)

    @app.get("/logs")
    def logs():
        return jsonify(lines=actions.tail_log())

    @app.get("/output/<path:name>")
    def output_file(name):
        return send_from_directory(config.OUTPUT_DIR, name, as_attachment=True)

    @app.post("/open-folder")
    def open_folder():
        path = (config.OUTPUT_DIR / request.form.get("path", "")).resolve()
        if not path.is_relative_to(config.OUTPUT_DIR.resolve()) or not path.is_dir():
            abort(404)
        os.startfile(path)  # ponytail: Windows-only; fine while the app runs locally
        return "", 204

    return app

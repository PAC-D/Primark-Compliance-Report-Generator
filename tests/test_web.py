from datetime import date
from io import BytesIO
from unittest.mock import patch

import pytest

from tps import actions
from tps.web.app import create_app
from tps.web.jobs import Job, JobRunner

UPLOAD_NAME = "Multi Search (Packaging Management)_2026_Jul_1-15.xlsx"


@pytest.fixture
def output(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    with patch("tps.actions.OUTPUT_DIR", out):
        yield out


@pytest.fixture
def runner():
    return JobRunner(inline=True)


@pytest.fixture
def client(output, runner):
    app = create_app(runner)
    app.testing = True
    return app.test_client()


def test_index_defaults_to_latest_month_with_data(client):
    with patch("tps.actions.latest_data_month", return_value=date(2026, 8, 1)):
        page = client.get("/").get_data(as_text=True)
    assert 'value="2026-08"' in page
    assert "Generate KPI report" in page


def test_kpi_job_links_its_pdf(client, output):
    pdf = output / "KPI_Report_June_2026.pdf"
    pdf.write_bytes(b"%PDF")
    with patch("tps.actions.generate_kpi_report",
               return_value=actions.Result("KPI report for June 2026", files=[pdf])) as kpi:
        job = client.post("/jobs/kpi", data={"month": "2026-06"}).get_json()

    assert kpi.call_args.args == (date(2026, 6, 1),)
    assert job["state"] == "done"
    assert job["result"]["files"] == ["KPI_Report_June_2026.pdf"]
    assert client.get("/output/KPI_Report_June_2026.pdf").data == b"%PDF"
    assert client.get("/job").get_json()["id"] == job["id"]


def test_failed_job_reports_its_error(client):
    with patch("tps.actions.generate_kpi_report", side_effect=ValueError("No data available")):
        job = client.post("/jobs/kpi", data={"month": "2026-09"}).get_json()
    assert job["state"] == "failed"
    assert job["error"] == "No data available"


def test_file_in_use_gets_a_readable_error(client):
    with patch("tps.actions.generate_summary_report",
               side_effect=PermissionError(13, "Permission denied", "Summary_Report_August_2026.xlsx")):
        job = client.post("/jobs/summary", data={"month": "2026-08"}).get_json()
    assert job["error"] == "Can't write Summary_Report_August_2026.xlsx - is it open in another program?"


def test_second_job_is_refused_while_one_runs(client, runner):
    runner.current = Job("abc", "Supplier reports - July 2026")  # still running
    response = client.post("/jobs/summary", data={"month": "2026-07"})
    assert response.status_code == 409
    assert "Supplier reports" in response.get_json()["error"]


def test_upload_keeps_original_file_names(client):
    seen = {}

    def load(paths, reprocess, progress):
        seen.update(names=[p.name for p in paths], exists=all(p.exists() for p in paths),
                    reprocess=reprocess)
        return actions.Result("Loaded 1 of 1 file(s)")

    with patch("tps.actions.load_transaction_files", side_effect=load):
        job = client.post("/jobs/upload", content_type="multipart/form-data", data={
            "files": [(BytesIO(b"x"), UPLOAD_NAME), (BytesIO(b"x"), "notes.txt")],
            "reprocess": "on",
        }).get_json()

    assert job["state"] == "done"
    assert seen == {"names": [UPLOAD_NAME], "exists": True, "reprocess": True}


def test_upload_without_excel_files_is_rejected(client):
    response = client.post("/jobs/upload", content_type="multipart/form-data",
                           data={"files": [(BytesIO(b"x"), "notes.txt")]})
    assert response.status_code == 400


def test_clear_passes_reload_choice(client):
    with patch("tps.actions.clear_database", return_value=actions.Result("Database cleared")) as clear:
        client.post("/jobs/clear", data={})
    assert clear.call_args.kwargs["reload"] is False


def test_output_cannot_escape_the_output_folder(client):
    assert client.get("/output/../config.yaml").status_code == 404
    assert client.post("/open-folder", data={"path": ".."}).status_code == 404


def test_logs(client):
    with patch("tps.actions.tail_log", return_value=["a", "b"]):
        assert client.get("/logs").get_json() == {"lines": ["a", "b"]}

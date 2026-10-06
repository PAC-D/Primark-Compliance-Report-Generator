from datetime import date
from io import BytesIO
from unittest.mock import patch

import pytest

from tps import actions
from tps.ingest import import_supplier_emails
from tps.web.app import create_app
from tps.web.jobs import Job, JobRunner

UPLOAD_NAME = "Multi Search (Packaging Management)_2026_Jul_1-15.xlsx"


@pytest.fixture
def output(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    with patch("tps.config.OUTPUT_DIR", out):
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
    assert "KPI Report" in page
    assert 'data-kind="all-supplier-data"' in page


def test_all_supplier_data_job_runs_the_combined_extract(client):
    with patch("tps.actions.extract_all_supplier_data",
               return_value=actions.Result("All supplier data for June 2026")) as extract:
        job = client.post("/jobs/all-supplier-data", data={"month": "2026-06"}).get_json()
    assert extract.call_args.args == (date(2026, 6, 1),)
    assert job["state"] == "done"


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


def test_cancel_stops_a_job_at_its_next_step(client, runner):
    def long_job(report_month, progress):
        progress(1, 3, "first")
        runner.cancel()  # as if the Cancel button was pressed now
        progress(2, 3, "second")
        raise AssertionError("not reached")

    with patch("tps.actions.generate_supplier_reports", side_effect=long_job):
        job = client.post("/jobs/supplier-reports", data={"month": "2026-07"}).get_json()
    assert job["state"] == "cancelled"
    assert job["done"] == 1


def test_month_status_paths_are_relative_to_output(client, output):
    kpi = output / "2026_August" / "KPI_Report_August_2026.pdf"
    with patch("tps.actions.month_status", return_value={
            "total_suppliers": 1, "total_factories": 1,
            "outputs": {"kpi": {"count": 1, "updated": "2026-10-04T20:00:00", "file": kpi},
                        "summary": None}}):
        status = client.get("/month/2026-08").get_json()
    assert status["outputs"]["kpi"]["file"] == "2026_August/KPI_Report_August_2026.pdf"
    assert status["outputs"]["summary"] is None


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


SUPPLIERS = [{"name": "ACME", "emails": "a@x.com, b@x.com", "region": "BD_Region", "months": {"2026-08": "BD_Region"}},
             {"name": "Bolt", "emails": "", "region": "CN_Region", "months": {}}]


def test_suppliers_list(client):
    with patch("tps.actions.supplier_list", return_value=SUPPLIERS):
        assert client.get("/suppliers").get_json() == SUPPLIERS


def test_save_supplier_emails(client):
    with patch("tps.actions.save_supplier_emails", return_value="a@x.com") as save:
        response = client.post("/suppliers/emails", data={"supplier": "ACME", "emails": "a@x.com,"})
    assert response.get_json() == {"emails": "a@x.com"}
    save.assert_called_once_with("ACME", "a@x.com,")


def test_exported_emails_import_back_unchanged(client, tmp_path):
    with patch("tps.actions.supplier_list", return_value=SUPPLIERS):
        response = client.get("/suppliers/export")
    assert response.headers["Content-Disposition"].startswith("attachment")
    path = tmp_path / "export.xlsx"
    path.write_bytes(response.data)

    stored = []
    with patch("tps.ingest.init_supplier_emails_table"), \
         patch("tps.ingest.set_supplier_emails", side_effect=stored.append):
        assert import_supplier_emails(path) == 1
    assert stored == [{"acme": ["a@x.com", "b@x.com"]}]

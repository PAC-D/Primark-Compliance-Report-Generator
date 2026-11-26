from datetime import date
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from tps import actions
from tps.ingest import import_supplier_emails
from tps.jobs import Job, JobRunner
from tps.metrics.dashboard import Filters

UPLOAD_NAME = "Multi Search (Packaging Management)_2026_Jul_1-15.xlsx"
ORIGIN = {"Origin": "http://localhost:3000"}


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
    return TestClient(create_app(runner), headers=ORIGIN)


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_latest_month(client):
    with patch("tps.actions.latest_data_month", return_value=date(2026, 8, 1)):
        assert client.get("/api/latest-month").json() == {"month": "2026-08"}


def test_supplier_compliance_passes_filters(client):
    with patch("api.routes.supplier_compliance", return_value={"ok": 1}) as sc:
        body = client.get("/api/supplier-compliance",
                          params={"month": "2026-08", "region": "BD", "supplier": "ACME", "country": ""}).json()
    assert body == {"ok": 1}
    assert sc.call_args.args == (Filters(date(2026, 8, 1), region="BD", supplier="ACME"),)


def test_kpi_all_region_means_no_filter(client):
    with patch("api.routes.kpi", return_value={"k": 1}) as kpi:
        client.get("/api/kpi", params={"month": "2026-08", "region": "all", "approved_by": "Sam"})
    assert kpi.call_args.args == (Filters(date(2026, 8, 1), approved_by="Sam"),)


def test_all_supplier_data_job_runs_the_combined_extract(client):
    with patch("tps.actions.extract_all_supplier_data",
               return_value=actions.Result("All supplier data for June 2026")) as extract:
        job = client.post("/api/jobs/all-supplier-data", data={"month": "2026-06"}).json()
    assert extract.call_args.args == (date(2026, 6, 1),)
    assert job["state"] == "done"


def test_unknown_job_kind_is_404(client):
    assert client.post("/api/jobs/nope", data={"month": "2026-06"}).status_code == 404


def test_kpi_job_links_its_pdf(client, output):
    pdf = output / "KPI_Report_June_2026.pdf"
    pdf.write_bytes(b"%PDF")
    with patch("tps.actions.generate_kpi_report",
               return_value=actions.Result("KPI report for June 2026", files=[pdf])) as kpi:
        job = client.post("/api/jobs/kpi", data={"month": "2026-06"}).json()

    assert kpi.call_args.args == (date(2026, 6, 1),)
    assert job["state"] == "done"
    assert job["result"]["files"] == ["KPI_Report_June_2026.pdf"]
    assert client.get("/api/output/KPI_Report_June_2026.pdf").content == b"%PDF"
    assert client.get("/api/job").json()["id"] == job["id"]


def test_selected_reports_job_passes_suppliers(client):
    with patch("tps.actions.generate_supplier_reports", return_value=actions.Result("ok")) as gen:
        client.post("/api/jobs/supplier-reports", data={"month": "2026-07", "supplier": ["ACME", "BOLT & CO"]})
    assert gen.call_args.args == (date(2026, 7, 1), ["ACME", "BOLT & CO"])


def test_reports_job_without_suppliers_means_all(client):
    with patch("tps.actions.generate_supplier_reports", return_value=actions.Result("ok")) as gen:
        client.post("/api/jobs/supplier-reports", data={"month": "2026-07"})
    assert gen.call_args.args == (date(2026, 7, 1), None)


def test_failed_job_reports_its_error(client):
    with patch("tps.actions.generate_kpi_report", side_effect=ValueError("No data available")):
        job = client.post("/api/jobs/kpi", data={"month": "2026-09"}).json()
    assert job["state"] == "failed"
    assert job["error"] == "No data available"


def test_missing_file_ends_as_job_error(client):
    with patch("tps.actions.generate_kpi_report", side_effect=FileNotFoundError("No transaction file")):
        job = client.post("/api/jobs/kpi", data={"month": "2026-09"}).json()
    assert job["state"] == "failed"
    assert job["error"] == "No transaction file"


def test_file_in_use_gets_a_readable_error(client):
    with patch("tps.actions.generate_summary_report",
               side_effect=PermissionError(13, "Permission denied", "Summary_Report_August_2026.xlsx")):
        job = client.post("/api/jobs/summary", data={"month": "2026-08"}).json()
    assert job["error"] == "Can't write Summary_Report_August_2026.xlsx - is it open in another program?"


def test_second_job_is_busy(client, runner):
    runner.current = Job("abc", "Supplier reports - July 2026")  # still running
    response = client.post("/api/jobs/summary", data={"month": "2026-07"})
    assert response.status_code == 409
    assert response.json() == {
        "error": "Supplier reports - July 2026 is still running. Wait for it to finish, or cancel it."}


def test_cancel_stops_a_job_at_its_next_step(client, runner):
    def long_job(report_month, suppliers, progress):
        progress(1, 3, "first")
        runner.cancel()
        progress(2, 3, "second")
        raise AssertionError("not reached")

    with patch("tps.actions.generate_supplier_reports", side_effect=long_job):
        job = client.post("/api/jobs/supplier-reports", data={"month": "2026-07"}).json()
    assert job["state"] == "cancelled"
    assert job["done"] == 1
    assert client.post("/api/job/cancel").json()["state"] == "cancelled"


def test_month_status_paths_are_relative_to_output(client, output):
    kpi = output / "2026_August" / "KPI_Report_August_2026.pdf"
    with patch("tps.actions.month_status", return_value={
            "total_suppliers": 1, "total_factories": 1,
            "outputs": {"kpi": {"count": 1, "updated": "2026-10-04T20:00:00", "file": kpi},
                        "summary": None}}):
        status = client.get("/api/month-status", params={"month": "2026-08"}).json()
    assert status["outputs"]["kpi"]["file"] == "2026_August/KPI_Report_August_2026.pdf"
    assert status["outputs"]["summary"] is None


def test_supplier_pdf_name_with_ampersand(client):
    name = "YIWU NANJI IMPORT & EXPORT CO LTD"

    def render(supplier, month, folder):
        pdf = folder / "x.pdf"
        pdf.write_bytes(b"%PDF-1")
        return pdf

    with patch("tps.actions._supplier_pdf", side_effect=render) as one, \
         patch("api.routes.close_browser") as close:
        response = client.get("/api/supplier-pdf?supplier=YIWU%20NANJI%20IMPORT%20%26%20EXPORT%20CO%20LTD&month=2026-07")
    assert one.call_args.args[:2] == (name, date(2026, 7, 1))
    assert response.content == b"%PDF-1"
    assert response.headers["content-disposition"].startswith("attachment")
    close.assert_called_once()


def test_supplier_pdf_renders_one_at_a_time(client):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    active, overlap = [0], []

    def render(supplier, month, folder):
        active[0] += 1
        overlap.append(active[0])
        time.sleep(0.05)
        active[0] -= 1
        pdf = folder / "x.pdf"
        pdf.write_bytes(b"%PDF-1")
        return pdf

    def get(_):
        return client.get("/api/supplier-pdf", params={"supplier": "ACME", "month": "2026-07"}).status_code

    with patch("tps.actions._supplier_pdf", side_effect=render), patch("api.routes.close_browser"):
        with ThreadPoolExecutor(2) as pool:
            codes = list(pool.map(get, range(2)))
    assert codes == [200, 200]
    assert max(overlap) == 1


def test_supplier_data_download(client):
    with patch("api.routes.supplier_workbook", return_value=b"xlsx") as wb:
        response = client.get("/api/supplier-data", params={"supplier": "ACME", "month": "2026-07"})
    assert response.content == b"xlsx"
    assert wb.call_args.args == ("ACME", date(2026, 7, 1))
    assert response.headers["content-disposition"].startswith("attachment")


def test_upload_keeps_original_file_names_and_cleans_up(client):
    seen = {}

    def load(paths, reprocess, progress):
        seen.update(names=[p.name for p in paths], exists=all(p.exists() for p in paths),
                    reprocess=reprocess, folder=paths[0].parent)
        return actions.Result("Loaded 1 of 1 file(s)")

    with patch("tps.actions.load_transaction_files", side_effect=load):
        job = client.post("/api/upload", data={"reprocess": "on"}, files=[
            ("files", (UPLOAD_NAME, BytesIO(b"x"))), ("files", ("notes.txt", BytesIO(b"x")))]).json()

    assert job["state"] == "done"
    assert (seen["names"], seen["exists"], seen["reprocess"]) == ([UPLOAD_NAME], True, True)
    assert not seen["folder"].exists()


def test_upload_name_cannot_escape_the_temp_folder(client):
    seen = {}

    def load(paths, reprocess, progress):
        seen["paths"] = paths
        return actions.Result("ok")

    with patch("tps.actions.load_transaction_files", side_effect=load):
        client.post("/api/upload", files=[("files", ("../../evil.xlsx", BytesIO(b"x")))])
    assert [p.name for p in seen["paths"]] == ["evil.xlsx"]


def test_upload_without_excel_files_is_rejected(client):
    response = client.post("/api/upload", files=[("files", ("notes.txt", BytesIO(b"x")))])
    assert response.status_code == 400
    assert response.json() == {"error": "Choose at least one Excel file (.xlsx)."}


def test_clear_runs_clear_database(client):
    with patch("tps.actions.clear_database", return_value=actions.Result("Database cleared")) as clear:
        client.post("/api/clear")
    clear.assert_called_once()


@pytest.mark.parametrize("headers", [{}, {"Origin": "https://evil.example"}])
def test_post_without_allowed_origin_is_refused(output, runner, headers):
    bare = TestClient(create_app(runner))
    with patch("tps.actions.clear_database") as clear:
        response = bare.post("/api/clear", headers=headers)
        upload = bare.post("/api/upload", headers=headers, files=[("files", ("a.xlsx", BytesIO(b"x")))])
    assert response.status_code == upload.status_code == 403
    assert response.json() == {"error": "Cross-site request refused"}
    clear.assert_not_called()


def test_allowed_origins_come_from_the_environment(output, runner, monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://a.example/, https://b.example")
    other = TestClient(create_app(runner), headers={"Origin": "https://a.example"})
    with patch("tps.actions.clear_database", return_value=actions.Result("x")):
        assert other.post("/api/clear").status_code == 200


def test_output_path_outside_is_404(client, output):
    (output.parent / "config.yaml").write_text("secret")
    assert client.get("/api/output/..%2Fconfig.yaml").status_code == 404
    assert client.get("/api/output/missing.pdf").status_code == 404


def test_logs(client):
    with patch("tps.actions.tail_log", return_value=["a", "b"]):
        assert client.get("/api/logs").json() == {"lines": ["a", "b"]}


SUPPLIERS = [{"name": "ACME", "emails": "a@x.com, b@x.com", "region": "BD_Region", "months": {"2026-08": "BD_Region"}},
             {"name": "Bolt", "emails": "", "region": "CN_Region", "months": {}}]


def test_suppliers_list(client):
    with patch("tps.actions.supplier_list", return_value=SUPPLIERS):
        assert client.get("/api/suppliers").json() == SUPPLIERS


def test_save_supplier_emails(client):
    with patch("tps.actions.save_supplier_emails", return_value="a@x.com") as save:
        response = client.post("/api/suppliers/emails", data={"supplier": "ACME", "emails": "a@x.com,"})
    assert response.json() == {"emails": "a@x.com"}
    save.assert_called_once_with("ACME", "a@x.com,")


def test_import_emails_job(client):
    with patch("tps.actions.import_emails", return_value=actions.Result("Imported")) as imp:
        job = client.post("/api/suppliers/import", files=[("file", ("emails.xlsx", BytesIO(b"x")))]).json()
    assert job["state"] == "done"
    assert imp.call_args.args[0].name == "emails.xlsx"


def test_exported_emails_import_back_unchanged(client, tmp_path):
    with patch("tps.actions.supplier_list", return_value=SUPPLIERS):
        response = client.get("/api/suppliers/export")
    assert response.headers["Content-Disposition"].startswith("attachment")
    path = tmp_path / "export.xlsx"
    path.write_bytes(response.content)

    stored = []
    with patch("tps.ingest.init_supplier_emails_table"), \
         patch("tps.ingest.set_supplier_emails", side_effect=stored.append):
        assert import_supplier_emails(path) == 1
    assert stored == [{"acme": ["a@x.com", "b@x.com"]}]


def test_supplier_pdf_inline_for_the_new_tab(client):
    def render(supplier, month, folder):
        pdf = folder / "x.pdf"
        pdf.write_bytes(b"%PDF-1")
        return pdf

    with patch("tps.actions._supplier_pdf", side_effect=render), patch("api.routes.close_browser"):
        response = client.get("/api/supplier-pdf", params={"supplier": "ACME", "month": "2026-07", "inline": "1"})
    assert response.headers["content-disposition"] == "inline; filename*=UTF-8''ACME_July_2026.pdf"


def test_supplier_data_zip(client):
    with patch("api.routes.supplier_data_zip", return_value=b"PK") as z:
        response = client.get("/api/supplier-data-zip?month=2026-07&supplier=A%20%26%20B&supplier=C")
    assert z.call_args.args == (["A & B", "C"], date(2026, 7, 1))
    assert response.content == b"PK"
    assert response.headers["content-disposition"] == "attachment; filename*=UTF-8''Supplier_Data_July_2026.zip"


def test_supplier_data_zip_with_no_data_is_404(client):
    with patch("api.routes.supplier_data_zip", return_value=None):
        response = client.get("/api/supplier-data-zip", params={"month": "2026-07", "supplier": "X"})
    assert response.status_code == 404
    assert response.json() == {"error": "None of these suppliers has data in July 2026."}


def test_options(client):
    with patch("api.routes.filter_options", return_value={"countries": ["China"], "approvers": []}) as opts:
        assert client.get("/api/options?month=2026-08").json() == {"countries": ["China"], "approvers": []}
    assert opts.call_args.args == (date(2026, 8, 1),)


def test_dashboard_endpoint(client):
    with patch("api.routes.summary_context", return_value={"d": date(2026, 8, 1), "suppliers_below": [], "email_map": {}}) as ctx:
        body = client.get("/api/dashboard", params={"month": "2026-08"}).json()
    ctx.assert_called_once_with(date(2026, 8, 1))
    assert body == {"d": "2026-08-01", "suppliers_below": [], "email_map": {}}


def test_supplier_endpoint_name_with_ampersand(client):
    with patch("api.routes.report_context", return_value={"kpis": {"total_lines": 3}}) as ctx:
        body = client.get("/api/supplier", params={"supplier": "BOLT & CO", "month": "2026-08"}).json()
    ctx.assert_called_once_with("BOLT & CO", date(2026, 8, 1), transactions=False)
    assert body["kpis"]["total_lines"] == 3


def test_supplier_without_lines_is_404(client):
    with patch("api.routes.report_context", return_value={"kpis": {"total_lines": 0}}):
        r = client.get("/api/supplier", params={"supplier": "ACME", "month": "2026-08"})
    assert r.status_code == 404 and r.json() == {"error": "No lines for this supplier in August 2026."}


def test_transactions_page_and_total(client):
    rows = [{"i": i} for i in range(50)]
    with patch("api.routes.get_transactions_page", return_value=(rows, 120)) as page:
        body = client.get("/api/supplier-transactions",
                          params={"supplier": "A", "month": "2026-08", "q": "po", "page": 2}).json()
        assert len(body["rows"]) == 50 and body["total"] == 120 and body["page"] == 2 and body["page_size"] == 50
        page.assert_called_with("A", date(2026, 8, 1), "po", 2, 50)
        body = client.get("/api/supplier-transactions",
                          params={"supplier": "A", "month": "2026-08", "page": 9}).json()
    assert body["page"] == 3


def test_search_endpoint(client):
    with patch("api.routes.search", return_value={"suppliers": ["A"], "factories": []}) as s:
        body = client.get("/api/search", params={"month": "2026-08", "q": "a"}).json()
    s.assert_called_once_with(date(2026, 8, 1), "a")
    assert body == {"suppliers": ["A"], "factories": []}


@pytest.mark.parametrize("path", ["/api/supplier-transactions", "/api/search"])
def test_bad_month_is_400_error(client, path):
    r = client.get(path, params={"supplier": "A", "month": "2026-13", "q": "x"})
    assert r.status_code == 400 and "error" in r.json()


def test_missing_param_uses_error_shape(client):
    r = client.get("/api/supplier", params={"month": "2026-08"})
    assert r.status_code == 400 and r.json() == {"error": "Missing or invalid: supplier"}


def test_dashboard_sends_only_the_follow_up_emails(client):
    context = {"suppliers_below": [{"supplier": " Acme "}],
               "email_map": {"acme": "a@x.com", "other": "o@x.com"}}
    with patch("api.routes.summary_context", return_value=context):
        body = client.get("/api/dashboard", params={"month": "2026-08"}).json()
    assert body["email_map"] == {"acme": "a@x.com"}

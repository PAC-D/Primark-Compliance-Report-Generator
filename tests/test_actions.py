from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tps import actions


@pytest.fixture(autouse=True)
def temp_output(tmp_path):
    """Nothing here may write to the real output/ folder."""
    out = tmp_path / "output"
    with patch("tps.config.OUTPUT_DIR", out):
        yield out


class TestLoadTransactionFiles:
    @pytest.fixture
    def files(self, tmp_path):
        paths = [tmp_path / "a.xlsx", tmp_path / "b.xlsx"]
        for p in paths:
            p.touch()
        return paths

    def _load(self, files, **kwargs):
        with patch("tps.actions.is_file_processed", side_effect=lambda p: Path(p).name == "a.xlsx"), \
             patch("tps.actions.process_file", return_value=10) as process, \
             patch("tps.actions.copy_to_data") as copy:
            result = actions.load_transaction_files(files, **kwargs)
        return result, [Path(c.args[0]).name for c in process.call_args_list], copy

    def test_skips_already_loaded_files(self, files):
        result, processed, copy = self._load(files)
        assert processed == ["b.xlsx"]
        assert result.summary == "Loaded 1 of 2 file(s)"
        assert "Already loaded, skipped: a.xlsx" in result.details
        copy.assert_called_once()

    def test_reprocess_loads_everything(self, files):
        result, processed, _ = self._load(files, reprocess=True)
        assert processed == ["a.xlsx", "b.xlsx"]

    def test_one_bad_file_does_not_stop_the_rest(self, files):
        with patch("tps.actions.is_file_processed", return_value=False), \
             patch("tps.actions.process_file", side_effect=[ValueError("bad sheet"), 5]), \
             patch("tps.actions.copy_to_data"):
            result = actions.load_transaction_files(files)
        assert result.summary == "Loaded 1 of 2 file(s)"
        assert "Failed a.xlsx: bad sheet" in result.details


class TestClearDatabase:
    def test_clear_only(self):
        with patch("tps.actions.clear_all_tables") as clear, \
             patch("tps.actions.load_transaction_files") as load:
            result = actions.clear_database(reload=False)
        clear.assert_called_once()
        load.assert_not_called()
        assert result.summary == "Database cleared (tables kept)"

    def test_clear_then_reload_data_folder(self, tmp_path):
        (tmp_path / "x.xlsx").touch()
        with patch("tps.actions.clear_all_tables"), \
             patch("tps.config.DATA_DIR", tmp_path), \
             patch("tps.actions.load_transaction_files",
                   return_value=actions.Result("Loaded 1 of 1 file(s)")) as load:
            actions.clear_database(reload=True)
        paths, = load.call_args.args
        assert [p.name for p in paths] == ["x.xlsx"]
        assert load.call_args.kwargs["reprocess"] is True
        assert load.call_args.kwargs["copy"] is False


class TestSupplierReports:
    def test_writes_region_folders_and_collects_failures(self, temp_output):
        def render(supplier, month):
            if supplier == "BAD LTD":
                raise RuntimeError("boom")
            return "<p>", "<l>"

        progress = MagicMock()
        with patch("tps.actions.get_suppliers_for_month", return_value=["ACME", "BAD LTD"]), \
             patch("tps.actions.get_supplier_kpis", return_value={"origin_country": "Bangladesh, China"}), \
             patch("tps.actions.render_report", side_effect=render), \
             patch("tps.actions.html_to_pdf_mixed") as pdf:
            result = actions.generate_supplier_reports(date(2026, 7, 1), progress)

        folder = temp_output / "2026_July" / "Supplier_Reports"
        pdf.assert_called_once_with("<p>", "<l>", str(folder / "CN_Region" / "ACME_July_2026.pdf"))
        assert result.folder == folder
        assert result.summary == "Generated 1 reports, 1 skipped"
        assert result.details == ["Skipped BAD LTD: boom"]
        assert progress.call_args_list[-1].args[:2] == (2, 2)

    def test_cancel_stops_handing_out_suppliers(self, temp_output):
        class Stop(Exception):
            pass

        def progress(done, total, message):
            if done == 1:
                raise Stop  # what the job runner does after Cancel

        suppliers = [f"S{i}" for i in range(40)]
        with patch("tps.actions.PDF_WORKERS", 1), \
             patch("tps.actions.get_suppliers_for_month", return_value=suppliers), \
             patch("tps.actions.get_supplier_kpis", return_value={"origin_country": "India"}), \
             patch("tps.actions.render_report", return_value=("<p>", "<l>")), \
             patch("tps.actions.html_to_pdf_mixed") as pdf:
            with pytest.raises(Stop):
                actions.generate_supplier_reports(date(2026, 7, 1), progress)
        assert pdf.call_count < len(suppliers)

    def test_month_without_suppliers(self):
        with patch("tps.actions.get_suppliers_for_month", return_value=[]):
            result = actions.generate_supplier_reports(date(2026, 9, 1))
        assert result.summary == "No suppliers with data in September 2026"


class TestKpiReport:
    def test_writes_pdf(self, temp_output):
        with patch("tps.actions.render_kpi_report", return_value="<html>KPI</html>"), \
             patch("tps.actions.html_to_pdf") as pdf, \
             patch("tps.actions.close_browser"):
            result = actions.generate_kpi_report(date(2026, 6, 1))
        path = temp_output / "2026_June" / "KPI_Report_June_2026.pdf"
        pdf.assert_called_once_with("<html>KPI</html>", str(path))
        assert result.files == [path]

    def test_no_data_raises(self):
        with patch("tps.actions.render_kpi_report", side_effect=ValueError("No data available")), \
             patch("tps.actions.html_to_pdf") as pdf:
            with pytest.raises(ValueError, match="No data"):
                actions.generate_kpi_report(date(2026, 6, 1))
        pdf.assert_not_called()


def test_summary_report_saved_to_output(temp_output):
    workbook = MagicMock()
    with patch("tps.actions.render_summary_excel", return_value=workbook):
        result = actions.generate_summary_report(date(2026, 8, 1))
    path = temp_output / "2026_August" / "Summary_Report_August_2026.xlsx"
    workbook.save.assert_called_once_with(path)
    assert result.files == [path]


def test_latest_data_month_falls_back_to_config_default():
    with patch("tps.actions.get_latest_data_month", return_value=None), \
         patch("tps.actions.get_report_month", return_value=date(2026, 9, 1)):
        assert actions.latest_data_month() == date(2026, 9, 1)


def test_tail_log(tmp_path):
    log = tmp_path / "run.log"
    log.write_text("\n".join(f"line {i}" for i in range(80)))
    with patch("tps.config.LOG_FILE", log):
        assert actions.tail_log(3) == ["line 77", "line 78", "line 79"]
    with patch("tps.config.LOG_FILE", tmp_path / "missing.log"):
        assert actions.tail_log() == []


def test_month_status_reads_the_month_folder(temp_output):
    month = temp_output / "2026_August"
    (month / "Supplier_Reports" / "BD_Region").mkdir(parents=True)
    (month / "Supplier_Reports" / "BD_Region" / "A_August_2026.pdf").write_bytes(b"%PDF")
    (month / "Supplier_Reports" / "BD_Region" / "B_August_2026.pdf").write_bytes(b"%PDF")
    (month / "KPI_Report_August_2026.pdf").write_bytes(b"%PDF")

    with patch("tps.actions.get_summary_sources", return_value={"total_suppliers": 2, "total_factories": 3}):
        status = actions.month_status(date(2026, 8, 1))

    assert status["total_suppliers"] == 2
    assert status["outputs"]["supplier-reports"]["count"] == 2
    assert status["outputs"]["kpi"]["file"] == month / "KPI_Report_August_2026.pdf"
    assert status["outputs"]["summary"] is None
    assert status["outputs"]["extract"] is None

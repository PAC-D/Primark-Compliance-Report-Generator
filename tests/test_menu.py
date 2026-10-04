from unittest.mock import patch

import pytest

from tps import menu


class TestMenuBanner:
    def test_banner_has_new_options(self, capsys):
        menu.print_banner()
        out = capsys.readouterr().out
        assert "[7] Generate KPI Report" in out
        assert "[8] Clear Database" in out


class TestClearDatabaseHandler:
    def test_clears_with_confirmation(self, capsys):
        # Decline the reload prompt: answering "y" there re-inserts every file
        # in data/ into the real database.
        with patch("tps.menu.clear_all_tables") as mock_clear, \
             patch("tps.menu.handle_reload_data") as mock_reload, \
             patch("builtins.input", side_effect=["y", "n"]):
            menu.handle_clear_database()
            mock_clear.assert_called_once()
            mock_reload.assert_not_called()

    def test_aborts_without_confirmation(self, capsys):
        with patch("tps.menu.clear_all_tables") as mock_clear, \
             patch("builtins.input", return_value="n"):
            menu.handle_clear_database()
            mock_clear.assert_not_called()


class TestKpiReportHandler:
    @pytest.fixture(autouse=True)
    def temp_output(self, tmp_path):
        # The handler deletes any existing report before writing; keep it off output/.
        with patch("tps.menu.OUTPUT_DIR", tmp_path):
            yield

    def test_generates_pdf(self):
        fake_html = "<html>KPI</html>"
        with patch("tps.menu.render_kpi_report", return_value=fake_html) as mock_render, \
             patch("tps.menu.html_to_pdf", return_value=True) as mock_pdf, \
             patch("builtins.input", side_effect=["2026", "6"]):
            menu.handle_generate_kpi_report()
            mock_render.assert_called_once()
            mock_pdf.assert_called_once()
            assert "KPI_Report" in str(mock_pdf.call_args[0][1])

    def test_no_data_prints_message(self, capsys):
        with patch("tps.menu.render_kpi_report", side_effect=ValueError("No data available")), \
             patch("tps.menu.html_to_pdf") as mock_pdf, \
             patch("builtins.input", side_effect=["2026", "6"]):
            menu.handle_generate_kpi_report()
            mock_pdf.assert_not_called()
            assert "No data" in capsys.readouterr().out

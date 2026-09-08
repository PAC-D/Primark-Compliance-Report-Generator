import sys
sys.path.insert(0, "..")

from datetime import date
from unittest.mock import patch, MagicMock

import pytest

import menu


class TestMenuBanner:
    def test_banner_has_new_options(self, capsys):
        menu.print_banner()
        out = capsys.readouterr().out
        assert "[7] Generate KPI Report" in out
        assert "[8] Clear Database" in out


class TestClearDatabaseHandler:
    def test_clears_with_confirmation(self, capsys):
        with patch("menu.clear_all_tables") as mock_clear, \
             patch("builtins.input", return_value="y"):
            menu.handle_clear_database()
            mock_clear.assert_called_once()

    def test_aborts_without_confirmation(self, capsys):
        with patch("menu.clear_all_tables") as mock_clear, \
             patch("builtins.input", return_value="n"):
            menu.handle_clear_database()
            mock_clear.assert_not_called()


class TestKpiReportHandler:
    def test_generates_pdf(self):
        fake_html = "<html>KPI</html>"
        with patch("menu.render_kpi_report", return_value=fake_html) as mock_render, \
             patch("menu.html_to_pdf", return_value=True) as mock_pdf, \
             patch("menu.input", side_effect=["2026", "6"]):
            menu.handle_generate_kpi_report()
            mock_render.assert_called_once()
            mock_pdf.assert_called_once()
            assert "KPI_Report" in str(mock_pdf.call_args[0][1])

    def test_no_data_prints_message(self, capsys):
        with patch("menu.render_kpi_report", side_effect=ValueError("No data available")), \
             patch("menu.html_to_pdf") as mock_pdf, \
             patch("menu.input", side_effect=["2026", "6"]):
            menu.handle_generate_kpi_report()
            mock_pdf.assert_not_called()
            assert "No data" in capsys.readouterr().out

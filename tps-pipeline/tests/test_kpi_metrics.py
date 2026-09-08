import sys
sys.path.insert(0, "..")

import calendar
from datetime import date
from unittest.mock import patch, MagicMock

import pytest

import kpi_metrics


class TestHelpers:
    def test_classify_region_bd(self):
        for c in ("Bangladesh", "India", "Pakistan", "Sri Lanka", "Morocco", "Turkey"):
            assert kpi_metrics.classify_region(c) == "BD"

    def test_classify_region_cn(self):
        assert kpi_metrics.classify_region("China") == "CN"
        assert kpi_metrics.classify_region("Cambodia") == "CN"
        assert kpi_metrics.classify_region("Unknown") == "CN"

    def test_month_label(self):
        assert kpi_metrics.month_label(date(2026, 6, 1)) == "Jun '26"
        assert kpi_metrics.month_label(date(2025, 12, 1)) == "Dec '25"

    def test_table_months_order(self):
        months = kpi_metrics.get_kpi_table_months(date(2026, 6, 1))
        assert months == [date(2026, 6, 1), date(2026, 5, 1), date(2025, 6, 1)]

    def test_table_months_january_rollover(self):
        months = kpi_metrics.get_kpi_table_months(date(2026, 1, 1))
        assert months == [date(2026, 1, 1), date(2025, 12, 1), date(2025, 1, 1)]

    def test_working_days_bd_excludes_fri_sat(self):
        assert kpi_metrics.working_days_in_month(2026, 3, (calendar.FRIDAY, calendar.SATURDAY)) == 23

    def test_working_days_cn_excludes_sat_sun(self):
        assert kpi_metrics.working_days_in_month(2026, 3, (calendar.SATURDAY, calendar.SUNDAY)) == 22

    def test_chart_months_no_data_falls_back(self):
        with patch("kpi_metrics.get_session") as mock_session:
            mock_session.return_value.execute.return_value.fetchone.return_value = None
            months = kpi_metrics.get_kpi_chart_months(date(2026, 6, 1))
            assert months == [date(2026, 6, 1)]

    def test_chart_months_full_12(self):
        with patch("kpi_metrics.get_session") as mock_session:
            row = MagicMock()
            row.min_date = date(2025, 1, 1)
            mock_session.return_value.execute.return_value.fetchone.return_value = row
            months = kpi_metrics.get_kpi_chart_months(date(2026, 6, 1))
            assert len(months) == 12
            assert months[0] == date(2025, 7, 1)
            assert months[-1] == date(2026, 6, 1)


class TestMonthlyTables:
    def test_three_months_with_data(self):
        with patch("kpi_metrics.get_session") as mock_session:
            inst = mock_session.return_value
            def fake_row(country, s, f, r):
                row = MagicMock()
                row.country, row.suppliers, row.factories, row.reflected_lines = country, s, f, r
                return row
            inst.execute.return_value.fetchall.side_effect = [
                [fake_row("Bangladesh", 2, 3, 10)],
                [fake_row("China", 1, 1, 5)],
                [fake_row("India", 1, 2, 4)],
            ]
            tables = kpi_metrics.get_kpi_monthly_tables(date(2026, 6, 1))
            assert [t["month_label"] for t in tables] == ["Jun '26", "May '26", "Jun '25"]
            assert tables[0]["rows"][0]["country"] == "Bangladesh"
            assert tables[0]["totals"] == {"suppliers": 2, "factories": 3, "reflected_lines": 10}

    def test_skips_empty_months(self):
        with patch("kpi_metrics.get_session") as mock_session:
            inst = mock_session.return_value
            inst.execute.return_value.fetchall.side_effect = [
                [MagicMock()], [], [MagicMock()]
            ]
            tables = kpi_metrics.get_kpi_monthly_tables(date(2026, 6, 1))
            assert [t["month_label"] for t in tables] == ["Jun '26", "Jun '25"]

    def test_no_data_returns_empty_list(self):
        with patch("kpi_metrics.get_session") as mock_session:
            mock_session.return_value.execute.return_value.fetchall.return_value = []
            tables = kpi_metrics.get_kpi_monthly_tables(date(2026, 6, 1))
            assert tables == []


class TestApprovedByPerformance:
    def test_skips_months_without_data(self):
        with patch("kpi_metrics.get_session") as mock_session, \
             patch("kpi_metrics.get_kpi_monthly_tables") as mock_tables:
            mock_tables.return_value = [
                {"month_label": "Jun '26", "rows": [MagicMock()], "totals": {}},
                {"month_label": "May '26", "rows": [MagicMock()], "totals": {}},
            ]
            inst = mock_session.return_value
            def fake_row(name, lines):
                row = MagicMock()
                row.approved_by, row.lines = name, lines
                return row
            inst.execute.return_value.fetchall.side_effect = [
                [fake_row("Alice", 5), fake_row("Bob", 3)],
                [fake_row("Alice", 7)],
            ]
            result = kpi_metrics.get_kpi_approved_by_performance(date(2026, 6, 1))
            assert result["month_labels"] == ["Jun '26", "May '26"]
            by_name = {r["approved_by"]: r["lines"] for r in result["rows"]}
            assert by_name["Alice"] == [5, 7]
            assert by_name["Bob"] == [3, 0]

    def test_no_data_returns_empty_rows_and_labels(self):
        with patch("kpi_metrics.get_session") as mock_session, \
             patch("kpi_metrics.get_kpi_monthly_tables") as mock_tables:
            mock_tables.return_value = []
            result = kpi_metrics.get_kpi_approved_by_performance(date(2026, 6, 1))
            assert result["rows"] == []
            assert result["month_labels"] == []


class TestAvgLinesPerDay:
    def test_calculation_for_march_2026(self):
        with patch("kpi_metrics.get_session") as mock_session:
            inst = mock_session.return_value
            def fake_row(val):
                row = MagicMock()
                row.__getitem__ = lambda self, key: val
                return row
            inst.execute.return_value.fetchone.side_effect = [fake_row(230), fake_row(154)]
            result = kpi_metrics.get_kpi_avg_lines_per_day(date(2026, 3, 1))
            assert result["bd"]["working_days"] == 23
            assert result["cn"]["working_days"] == 22
            assert result["bd"]["lines"] == 230
            assert result["cn"]["lines"] == 154
            assert result["bd"]["avg"] == 10
            assert result["cn"]["avg"] == 7

    def test_avg_rounds_up_to_whole_number(self):
        with patch("kpi_metrics.get_session") as mock_session:
            inst = mock_session.return_value
            def fake_row(val):
                row = MagicMock()
                row.__getitem__ = lambda self, key: val
                return row
            inst.execute.return_value.fetchone.side_effect = [fake_row(231), fake_row(45)]
            result = kpi_metrics.get_kpi_avg_lines_per_day(date(2026, 3, 1))
            assert result["bd"]["avg"] == 11   # 231/23 = 10.04 -> ceil = 11
            assert result["cn"]["avg"] == 3    # 45/22 = 2.045 -> ceil = 3

    def test_no_data_returns_zero(self):
        with patch("kpi_metrics.get_session") as mock_session:
            mock_session.return_value.execute.return_value.fetchone.return_value = None
            result = kpi_metrics.get_kpi_avg_lines_per_day(date(2026, 3, 1))
            assert result["bd"]["lines"] == 0
            assert result["bd"]["avg"] == 0.0
            assert result["cn"]["lines"] == 0
            assert result["cn"]["avg"] == 0.0


class TestSupplierFactoryTrend:
    def test_returns_counts_per_month(self):
        with patch("kpi_metrics.get_session") as mock_session, \
             patch("kpi_metrics.get_kpi_chart_months") as mock_range:
            mock_range.return_value = [date(2026, 5, 1), date(2026, 6, 1)]
            inst = mock_session.return_value
            def fake_row(s, f):
                row = MagicMock()
                row.suppliers, row.factories = s, f
                return row
            inst.execute.return_value.fetchone.side_effect = [fake_row(10, 15), fake_row(12, 18)]
            result = kpi_metrics.get_kpi_supplier_factory_trend(date(2026, 6, 1))
            assert result["labels"] == ["May '26", "Jun '26"]
            assert result["suppliers"] == [10, 12]
            assert result["factories"] == [15, 18]

    def test_no_data_returns_zeros(self):
        with patch("kpi_metrics.get_session") as mock_session, \
             patch("kpi_metrics.get_kpi_chart_months") as mock_range:
            mock_range.return_value = [date(2026, 6, 1)]
            mock_session.return_value.execute.return_value.fetchone.return_value = None
            result = kpi_metrics.get_kpi_supplier_factory_trend(date(2026, 6, 1))
            assert result["suppliers"] == [0]
            assert result["factories"] == [0]


class TestRegionReflectedLines:
    def test_classifies_countries_per_month(self):
        with patch("kpi_metrics.get_session") as mock_session, \
             patch("kpi_metrics.get_kpi_chart_months") as mock_range:
            mock_range.return_value = [date(2026, 5, 1), date(2026, 6, 1)]
            inst = mock_session.return_value
            def fake_row(country, lines):
                row = MagicMock()
                row.country, row.lines = country, lines
                return row
            inst.execute.return_value.fetchall.side_effect = [
                [fake_row("Bangladesh", 10), fake_row("China", 5)],
                [fake_row("India", 8), fake_row("Cambodia", 2)],
            ]
            result = kpi_metrics.get_kpi_region_reflected_lines(date(2026, 6, 1))
            assert result["labels"] == ["May '26", "Jun '26"]
            assert result["bd"] == [10, 8]
            assert result["cn"] == [5, 2]

    def test_empty_months_zero(self):
        with patch("kpi_metrics.get_session") as mock_session, \
             patch("kpi_metrics.get_kpi_chart_months") as mock_range:
            mock_range.return_value = [date(2026, 6, 1)]
            mock_session.return_value.execute.return_value.fetchall.return_value = []
            result = kpi_metrics.get_kpi_region_reflected_lines(date(2026, 6, 1))
            assert result["bd"] == [0]
            assert result["cn"] == [0]

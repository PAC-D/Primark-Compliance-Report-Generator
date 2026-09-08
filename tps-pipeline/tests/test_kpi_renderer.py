import sys
sys.path.insert(0, "..")

from datetime import date
from unittest.mock import patch, MagicMock

import pytest

import kpi_renderer


@pytest.fixture
def mock_metrics():
    with patch.multiple(
        "kpi_renderer",
        get_kpi_monthly_tables=MagicMock(return_value=[]),
        get_kpi_approved_by_performance=MagicMock(
            return_value={"month_labels": ["Jun '26", "May '26", "Jun '25"], "rows": []}
        ),
        get_kpi_avg_lines_per_day=MagicMock(
            return_value={
                "bd": {"region": "BD", "lines": 230, "working_days": 23, "avg": 10.0},
                "cn": {"region": "CN", "lines": 154, "working_days": 22, "avg": 7.0},
            }
        ),
        get_kpi_supplier_factory_trend=MagicMock(
            return_value={"labels": ["Jun '26"], "suppliers": [10], "factories": [15]}
        ),
        get_kpi_region_reflected_lines=MagicMock(
            return_value={"labels": ["Jun '26"], "bd": [100], "cn": [50]}
        ),
    ):
        yield


class TestRenderKpiReport:
    def test_renders_full_html(self, mock_metrics):
        html = kpi_renderer.render_kpi_report(date(2026, 6, 1))
        assert "Transit Packaging System (TPS) KPI Report" in html
        assert "Individual Performance" in html
        assert "Individual Performance (Approved By)" not in html
        assert "Average Lines Processed Per Day" in html
        assert html.count('class="page-header"') == 2
        assert html.count('class="page-footer"') == 2
        assert "page-break" in html
        assert "month-cards" in html
        assert "chartTrend" in html
        assert "chartRegion" in html
        assert "chartBdLines" not in html
        assert "chartCnLines" not in html

    def test_raises_when_no_data(self):
        with patch.multiple(
            "kpi_renderer",
            get_kpi_monthly_tables=MagicMock(return_value=[]),
            get_kpi_approved_by_performance=MagicMock(return_value={"month_labels": [], "rows": []}),
            get_kpi_avg_lines_per_day=MagicMock(
                return_value={
                    "bd": {"region": "BD", "lines": 0, "working_days": 23, "avg": 0.0},
                    "cn": {"region": "CN", "lines": 0, "working_days": 22, "avg": 0.0},
                }
            ),
            get_kpi_supplier_factory_trend=MagicMock(return_value={"labels": [], "suppliers": [], "factories": []}),
            get_kpi_region_reflected_lines=MagicMock(return_value={"labels": [], "bd": [], "cn": []}),
        ):
            with pytest.raises(ValueError, match="No data available"):
                kpi_renderer.render_kpi_report(date(2026, 6, 1))

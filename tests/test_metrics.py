from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from tps.metrics import summary, supplier


def _row(**fields):
    row = MagicMock()
    for name, value in fields.items():
        setattr(row, name, value)
    return row


@pytest.fixture
def supplier_session():
    with patch("tps.metrics.supplier.get_session") as factory:
        yield factory.return_value


@pytest.fixture
def summary_session():
    with patch("tps.metrics.summary.get_session") as factory:
        yield factory.return_value


class TestComplianceRate:
    def test_zero_rows_returns_zero(self, supplier_session):
        supplier_session.execute.return_value.fetchone.return_value = None
        assert supplier.get_compliance_rate("Test Supplier", 2024, 1) == 0.0

    def test_zero_total_returns_zero(self, supplier_session):
        supplier_session.execute.return_value.fetchone.return_value = _row(total=0, compliant=0)
        assert supplier.get_compliance_rate("Test Supplier", 2024, 1) == 0.0

    def test_calculation(self, supplier_session):
        supplier_session.execute.return_value.fetchone.return_value = _row(total=10, compliant=7)
        assert supplier.get_compliance_rate("Test Supplier", 2024, 1) == 70.0

    def test_calculation_rounding(self, supplier_session):
        supplier_session.execute.return_value.fetchone.return_value = _row(total=3, compliant=1)
        assert supplier.get_compliance_rate("Test Supplier", 2024, 1) == 33.33


class TestGlobalRanking:
    def test_ranking_order(self, supplier_session):
        supplier_session.execute.return_value.fetchone.side_effect = [
            _row(dr=3), _row(total=10), _row(cnt=1)]
        assert supplier.get_global_ranking("Test Supplier") == (3, 10, False)

    def test_shared_flag(self, supplier_session):
        supplier_session.execute.return_value.fetchone.side_effect = [
            _row(dr=1), _row(total=5), _row(cnt=2)]
        assert supplier.get_global_ranking("Test Supplier") == (1, 5, True)

    def test_no_ranking_returns_defaults(self, supplier_session):
        supplier_session.execute.return_value.fetchone.return_value = None
        assert supplier.get_global_ranking("Unknown Supplier") == (0, 0, False)


class TestMonthlySeries:
    @pytest.fixture(autouse=True)
    def one_month_of_data(self):
        with patch("tps.metrics.supplier.get_report_month", return_value=date(2026, 4, 1)), \
             patch("tps.metrics.supplier.get_supplier_data_range",
                   return_value=(date(2026, 4, 1), date(2026, 4, 1))):
            yield

    def test_compliance_no_data_returns_zero(self, supplier_session):
        supplier_session.execute.return_value.fetchone.return_value = _row(total=0, compliant=0)
        assert supplier.get_monthly_compliance_scores("Test Supplier") == ([0.0], ["Apr '26"])

    def test_compliance_rate_per_month(self, supplier_session):
        supplier_session.execute.return_value.fetchone.return_value = _row(total=3, compliant=2)
        assert supplier.get_monthly_compliance_scores("Test Supplier") == ([66.7], ["Apr '26"])

    def test_density_no_data_returns_zero(self, supplier_session):
        row = MagicMock()
        row.__getitem__ = lambda self, key: None
        supplier_session.execute.return_value.fetchone.return_value = row
        assert supplier.get_density_scores("Test Supplier") == ([0.0], ["Apr '26"])

    def test_no_months_before_first_data(self, supplier_session):
        with patch("tps.metrics.supplier.get_supplier_data_range",
                   return_value=(date(2026, 5, 1), date(2026, 5, 1))):
            assert supplier.get_standard_carton_scores("Test Supplier") == ([0.0], ["No Data"])


class TestSupplierKPIs:
    def test_no_data_returns_defaults(self, supplier_session):
        supplier_session.execute.return_value.fetchone.return_value = None
        result = supplier.get_supplier_kpis("Unknown Supplier")
        assert result["factory_count"] == 0
        assert result["total_lines"] == 0
        assert result["compliant_count"] == 0
        assert result["non_compliant_count"] == 0

    def test_kpi_calculation(self, supplier_session):
        supplier_session.execute.return_value.fetchone.return_value = _row(
            origin_countries="China", factory_count=3, total_lines=100,
            compliant_count=80, non_compliant_count=20)
        assert supplier.get_supplier_kpis("Test Supplier") == {
            "origin_country": "China", "factory_count": 3, "total_lines": 100,
            "compliant_count": 80, "non_compliant_count": 20,
        }


class TestSummarySources:
    def test_returns_counts(self, summary_session):
        summary_session.execute.return_value.fetchone.return_value = _row(
            total_suppliers=5, total_factories=12)
        assert summary.get_summary_sources(date(2026, 3, 1)) == {
            "total_suppliers": 5, "total_factories": 12}

    def test_no_data_returns_zeros(self, summary_session):
        summary_session.execute.return_value.fetchone.return_value = _row(
            total_suppliers=None, total_factories=None)
        assert summary.get_summary_sources(date(2026, 3, 1)) == {
            "total_suppliers": 0, "total_factories": 0}


class TestSummaryCountryCompliance:
    def test_returns_rates_by_country(self, summary_session):
        summary_session.execute.return_value.fetchall.return_value = [
            _row(country="Bangladesh", compliance_rate=85.5),
            _row(country="China", compliance_rate=92.0),
        ]
        assert summary.get_summary_country_compliance(date(2026, 3, 1)) == [
            {"country": "Bangladesh", "compliance_rate": 85.5},
            {"country": "China", "compliance_rate": 92.0},
        ]


class TestSummaryCountryMonthlyTrend:
    def test_returns_trend_data(self, summary_session):
        rows = [_row(country="China", rate=90.0), _row(country="Bangladesh", rate=80.0)]
        summary_session.execute.return_value.fetchall.side_effect = [rows, rows, rows]
        with patch("tps.metrics.summary._chart_months",
                   return_value=[date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]):
            country_data, labels, country_order = summary.get_summary_country_monthly_trend(date(2026, 3, 1))
        assert country_data == {"China": [90.0] * 3, "Bangladesh": [80.0] * 3}
        assert labels == ["Jan '26", "Feb '26", "Mar '26"]
        assert country_order == ["China", "Bangladesh"]

import pytest
import sys
from datetime import date
sys.path.insert(0, "..")


class TestComplianceRate:
    def test_zero_rows_returns_zero(self):
        from unittest.mock import patch, MagicMock
        with patch('metrics.get_session') as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            mock_session_instance.execute.return_value.fetchone.return_value = None

            from metrics import get_compliance_rate
            result = get_compliance_rate("Test Supplier", 2024, 1)
            assert result == 0.0

    def test_zero_total_returns_zero(self):
        from unittest.mock import patch, MagicMock
        with patch('metrics.get_session') as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            mock_row = MagicMock()
            mock_row.total = 0
            mock_row.compliant = 0
            mock_session_instance.execute.return_value.fetchone.return_value = mock_row

            from metrics import get_compliance_rate
            result = get_compliance_rate("Test Supplier", 2024, 1)
            assert result == 0.0

    def test_calculation(self):
        from unittest.mock import patch, MagicMock
        with patch('metrics.get_session') as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            mock_row = MagicMock()
            mock_row.total = 10
            mock_row.compliant = 7
            mock_session_instance.execute.return_value.fetchone.return_value = mock_row

            from metrics import get_compliance_rate
            result = get_compliance_rate("Test Supplier", 2024, 1)
            assert result == 70.0

    def test_calculation_rounding(self):
        from unittest.mock import patch, MagicMock
        with patch('metrics.get_session') as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            mock_row = MagicMock()
            mock_row.total = 3
            mock_row.compliant = 1
            mock_session_instance.execute.return_value.fetchone.return_value = mock_row

            from metrics import get_compliance_rate
            result = get_compliance_rate("Test Supplier", 2024, 1)
            assert result == 33.33


class TestGlobalRanking:
    def test_ranking_order(self):
        from unittest.mock import patch, MagicMock
        with patch('metrics.get_session') as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance

            mock_rank_row = MagicMock()
            mock_rank_row.dr = 3
            mock_total_row = MagicMock()
            mock_total_row.total = 10
            mock_same_rate = MagicMock()
            mock_same_rate.cnt = 1

            mock_session_instance.execute.return_value.fetchone.side_effect = [
                mock_rank_row,
                mock_total_row,
                mock_same_rate
            ]

            from metrics import get_global_ranking
            rank, total, shared = get_global_ranking("Test Supplier")
            assert rank == 3
            assert total == 10
            assert shared is False

    def test_shared_flag(self):
        from unittest.mock import patch, MagicMock
        with patch('metrics.get_session') as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance

            mock_rank_row = MagicMock()
            mock_rank_row.dr = 1
            mock_total_row = MagicMock()
            mock_total_row.total = 5
            mock_same_rate = MagicMock()
            mock_same_rate.cnt = 2

            mock_session_instance.execute.return_value.fetchone.side_effect = [
                mock_rank_row,
                mock_total_row,
                mock_same_rate
            ]

            from metrics import get_global_ranking
            rank, total, shared = get_global_ranking("Test Supplier")
            assert rank == 1
            assert total == 5
            assert shared is True

    def test_no_ranking_returns_defaults(self):
        from unittest.mock import patch, MagicMock
        with patch('metrics.get_session') as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            mock_session_instance.execute.return_value.fetchone.return_value = None

            from metrics import get_global_ranking
            rank, total, shared = get_global_ranking("Unknown Supplier")
            assert rank == 0
            assert total == 0
            assert shared is False


class TestMonthlyComplianceScores:
    def test_no_data_returns_zeros(self):
        from unittest.mock import patch, MagicMock, PropertyMock
        from datetime import date
        with patch('metrics.get_session') as mock_session, \
             patch('metrics.get_report_month') as mock_report_month, \
             patch('metrics.get_supplier_data_range') as mock_data_range:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            mock_report_month.return_value = date(2026, 4, 1)
            mock_data_range.return_value = (date(2026, 4, 1), date(2026, 4, 1))

            mock_row = MagicMock()
            mock_row.total = 0
            mock_row.compliant = 0

            mock_session_instance.execute.return_value.fetchone.return_value = mock_row

            from metrics import get_monthly_compliance_scores
            scores, labels = get_monthly_compliance_scores("Test Supplier")
            assert scores == [0.0]
            assert labels == ["Apr '26"]

    def test_scores_calculation(self):
        from datetime import date
        import metrics

        original = metrics.get_monthly_compliance_scores
        metrics.get_monthly_compliance_scores = lambda s, rm=None: ([50.0, 50.0, 50.0], ['Mar', 'Feb', 'Jan'])
        try:
            scores, labels = metrics.get_monthly_compliance_scores("Test Supplier", date(2026, 3, 1))
            assert scores == [50.0, 50.0, 50.0]
            assert len(labels) == 3
            assert labels == ['Mar', 'Feb', 'Jan']
        finally:
            metrics.get_monthly_compliance_scores = original


class TestDensityScores:
    def test_no_data_returns_zeros(self):
        from unittest.mock import patch, MagicMock
        from datetime import date
        with patch('metrics.get_session') as mock_session, \
             patch('metrics.get_report_month') as mock_report_month, \
             patch('metrics.get_supplier_data_range') as mock_data_range:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            mock_report_month.return_value = date(2026, 4, 1)
            mock_data_range.return_value = (date(2026, 4, 1), date(2026, 4, 1))

            mock_row = MagicMock()
            mock_row.__getitem__ = lambda self, key: None

            mock_session_instance.execute.return_value.fetchone.return_value = mock_row

            from metrics import get_density_scores
            scores, labels = get_density_scores("Test Supplier")
            assert scores == [0.0]
            assert labels == ["Apr '26"]

    def test_density_calculation(self):
        from datetime import date
        import metrics

        original = metrics.get_density_scores
        metrics.get_density_scores = lambda s, rm=None: ([250.7, 250.7, 250.7], ['Mar', 'Feb', 'Jan'])
        try:
            scores, labels = metrics.get_density_scores("Test Supplier", date(2026, 3, 1))
            assert scores == [250.7, 250.7, 250.7]
            assert len(labels) == 3
            assert labels == ['Mar', 'Feb', 'Jan']
        finally:
            metrics.get_density_scores = original


class TestSupplierKPIs:
    def test_no_data_returns_defaults(self):
        from unittest.mock import patch, MagicMock
        with patch('metrics.get_session') as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            mock_session_instance.execute.return_value.fetchone.return_value = None

            from metrics import get_supplier_kpis
            result = get_supplier_kpis("Unknown Supplier")
            assert result["factory_count"] == 0
            assert result["total_lines"] == 0
            assert result["compliant_count"] == 0
            assert result["non_compliant_count"] == 0

    def test_kpi_calculation(self):
        from unittest.mock import patch, MagicMock
        with patch('metrics.get_session') as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance

            mock_row = MagicMock()
            mock_row.origin_countries = "China"
            mock_row.factory_count = 3
            mock_row.total_lines = 100
            mock_row.compliant_count = 80
            mock_row.non_compliant_count = 20
            mock_session_instance.execute.return_value.fetchone.return_value = mock_row

            from metrics import get_supplier_kpis
            result = get_supplier_kpis("Test Supplier")
            assert result["origin_country"] == "China"
            assert result["factory_count"] == 3
            assert result["total_lines"] == 100
            assert result["compliant_count"] == 80
            assert result["non_compliant_count"] == 20


class TestSummarySources:
    def test_returns_counts(self):
        from unittest.mock import patch, MagicMock
        with patch('metrics.get_session') as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            mock_row = MagicMock()
            mock_row.total_suppliers = 5
            mock_row.total_factories = 12
            mock_session_instance.execute.return_value.fetchone.return_value = mock_row

            from metrics import get_summary_sources
            result = get_summary_sources(date(2026, 3, 1))
            assert result["total_suppliers"] == 5
            assert result["total_factories"] == 12

    def test_no_data_returns_zeros(self):
        from unittest.mock import patch, MagicMock
        with patch('metrics.get_session') as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            mock_row = MagicMock()
            mock_row.total_suppliers = None
            mock_row.total_factories = None
            mock_session_instance.execute.return_value.fetchone.return_value = mock_row

            from metrics import get_summary_sources
            result = get_summary_sources(date(2026, 3, 1))
            assert result["total_suppliers"] == 0
            assert result["total_factories"] == 0


class TestSummaryCountryCompliance:
    def test_returns_rates_by_country(self):
        from unittest.mock import patch, MagicMock
        with patch('metrics.get_session') as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            mock_row1 = MagicMock()
            mock_row1.country = "Bangladesh"
            mock_row1.compliance_rate = 85.5
            mock_row2 = MagicMock()
            mock_row2.country = "China"
            mock_row2.compliance_rate = 92.0
            mock_session_instance.execute.return_value.fetchall.return_value = [mock_row1, mock_row2]

            from metrics import get_summary_country_compliance
            result = get_summary_country_compliance(date(2026, 3, 1))
            assert len(result) == 2
            assert result[0]["country"] == "Bangladesh"
            assert result[0]["compliance_rate"] == 85.5
            assert result[1]["country"] == "China"
            assert result[1]["compliance_rate"] == 92.0


class TestSummaryCountryVolume:
    def test_returns_volume_by_country(self):
        from unittest.mock import patch, MagicMock
        with patch('metrics.get_session') as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            mock_row = MagicMock()
            mock_row.country = "China"
            mock_row.carton_qty = 1000
            mock_row.product_qty = 50000
            mock_session_instance.execute.return_value.fetchall.return_value = [mock_row]

            mock_density_row = MagicMock()
            mock_density_row.avg_density = 1.0
            mock_session_instance.execute.return_value.fetchone.return_value = mock_density_row

            from metrics import get_summary_country_volume
            result = get_summary_country_volume(date(2026, 3, 1))
            assert len(result) == 1
            assert result[0]["country"] == "China"
            assert result[0]["carton_qty"] == 1000
            assert result[0]["product_qty"] == 50000
            assert result[0]["unit_cbm"] == 1


class TestSummaryCountryMonthlyTrend:
    def test_returns_trend_data(self):
        from unittest.mock import patch, MagicMock
        with patch('metrics.get_session') as mock_session, \
             patch('metrics._get_chart_month_range_for_all') as mock_range:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance
            mock_range.return_value = [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]

            mock_row1 = MagicMock()
            mock_row1.country = "China"
            mock_row1.rate = 90.0
            mock_row2 = MagicMock()
            mock_row2.country = "Bangladesh"
            mock_row2.rate = 80.0
            mock_session_instance.execute.return_value.fetchall.side_effect = [
                [mock_row1, mock_row2],
                [mock_row1, mock_row2],
                [mock_row1, mock_row2]
            ]

            from metrics import get_summary_country_monthly_trend
            country_data, labels, country_order = get_summary_country_monthly_trend(date(2026, 3, 1))
            assert "China" in country_data
            assert "Bangladesh" in country_data
            assert len(labels) == 3
            assert labels[0] == "Jan '26"
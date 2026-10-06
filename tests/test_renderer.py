from datetime import date
from unittest.mock import patch

import pytest

from tps.reports import supplier_report

EMPTY_TOTALS = {"dest_po_count": 0, "reflected_lines": 0, "pending": 0,
                "approved": 0, "rejected": 0, "escalated": 0}


@pytest.fixture
def metrics():
    """Every metric the supplier report reads, stubbed with one month of data."""
    with patch.multiple(
        "tps.reports.supplier_report",
        get_supplier_kpis=lambda *a: {"origin_country": "China", "factory_count": 2, "total_lines": 100,
                                      "compliant_count": 80, "non_compliant_count": 20},
        get_global_ranking=lambda *a: (3, 10, False),
        get_local_rankings=lambda *a: [{"country": "China", "rank": 3, "total": 10, "shared": False}],
        get_compliance_rate=lambda *a: 80.0,
        get_monthly_compliance_scores=lambda *a: ([80.0] * 12, ["Jan"] * 12),
        get_standard_carton_scores=lambda *a: ([70.0] * 12, ["Jan"] * 12),
        get_density_scores=lambda *a: ([250.0] * 12, ["Jan"] * 12),
        get_associated_factories=lambda *a: [{"factory": "Factory A", "origin_countries": "China", "compliance_rate": 80.0},
                                             {"factory": "Factory B", "origin_countries": "China", "compliance_rate": 10.0}],
        get_line_details=lambda *a: ([], EMPTY_TOTALS),
        get_compliance_data=lambda *a: [{"factory": "Factory A", "standard_carton_pct": 80.0,
                                         "total_carton_qty": 1000, "corrugated_sqm": 50.0}],
        get_transactions=lambda *a: [],
    ):
        yield


def test_renders_one_document(metrics):
    html = supplier_report.render_report("Test Supplier", date(2024, 1, 1))

    assert html.startswith("<!DOCTYPE html>")
    assert "Test Supplier" in html
    assert "January 2024" in html
    for section in ("Associated Factories", "Line Details", "Standard Carton Usage", "Transaction Details"):
        assert section in html
    assert 'class="shared"' not in html


def test_factory_band_counts(metrics):
    html = supplier_report.render_report("Test Supplier", date(2024, 1, 1))
    assert '<i class="tone-high" style="flex:1">' in html
    assert '<i class="tone-low" style="flex:1">' in html
    assert 'class="tone-mid" style="flex' not in html


def test_shared_ranks_are_badged(metrics):
    with patch("tps.reports.supplier_report.get_global_ranking", return_value=(1, 10, True)), \
         patch("tps.reports.supplier_report.get_local_rankings",
               return_value=[{"country": "China", "rank": 1, "total": 10, "shared": True}]):
        html = supplier_report.render_report("Test Supplier", date(2024, 1, 1))
    assert html.count('class="shared"') == 2


def test_defaults_to_report_month(metrics):
    with patch("tps.reports.supplier_report.get_report_month", return_value=date(2024, 1, 1)) as default:
        supplier_report.render_report("Test Supplier")
    default.assert_called_once()


@pytest.mark.parametrize("rate, band", [(100, "high"), (70, "high"), (69.99, "mid"), (40, "mid"), (39.9, "low"), (0, "low")])
def test_rate_bands(rate, band):
    assert supplier_report.rate_band(rate) == band

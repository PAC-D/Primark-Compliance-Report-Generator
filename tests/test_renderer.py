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
        get_associated_factories=lambda *a: [{"factory": "Factory A", "origin_countries": "China",
                                              "compliance_rate": 80.0}],
        get_line_details=lambda *a: ([], EMPTY_TOTALS),
        get_compliance_data=lambda *a: [{"factory": "Factory A", "standard_carton_pct": 80.0,
                                         "total_carton_qty": 1000, "corrugated_sqm": 50.0}],
        get_transactions=lambda *a: [],
    ):
        yield


def test_renders_portrait_and_landscape(metrics):
    portrait_html, landscape_html = supplier_report.render_report("Test Supplier", date(2024, 1, 1))

    assert "PRIMARK" in portrait_html
    assert "Test Supplier" in portrait_html
    assert "January" in portrait_html
    assert "CORRUGATED" in portrait_html.upper()
    assert supplier_report.LANDSCAPE_MARKER not in portrait_html
    assert landscape_html.startswith("<!DOCTYPE html>")


def test_defaults_to_report_month(metrics):
    with patch("tps.reports.supplier_report.get_report_month", return_value=date(2024, 1, 1)) as default:
        supplier_report.render_report("Test Supplier")
    default.assert_called_once()


@pytest.mark.parametrize("rate, colour", [(85, "#059669"), (50, "#f59e0b"), (10, "#e31837")])
def test_gauge_colour_bands(rate, colour):
    assert supplier_report._make_gauge_arc(rate)["color"] == colour


def test_gauge_clamps_rate():
    assert supplier_report._make_gauge_arc(140)["rate"] == 100
    assert supplier_report._make_gauge_arc(-5)["dasharray"] == "0.0 283"

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


def test_report_escapes_supplier_name(metrics):
    html = supplier_report.render_report("A <B> & C", date(2024, 1, 1))
    assert "A &lt;B&gt; &amp; C" in html
    assert "A <B> & C" not in html


BLURRED_SHADOW = r"box-shadow:\s*[-\d.]+(?:px)?\s+[-\d.]+(?:px)?\s+[1-9]"


def test_report_has_no_blurred_shadows(metrics):
    import re
    html = supplier_report.render_report("Test Supplier", date(2024, 1, 1))
    assert not re.search(BLURRED_SHADOW, html)


def test_report_charts_use_high_dpr(metrics):
    assert "devicePixelRatio:3" in supplier_report.render_report("Test Supplier", date(2024, 1, 1))


# --- Shared contexts ------------------------------------------------------------

def test_report_context_without_transactions(metrics):
    ctx = supplier_report.report_context("Test Supplier", date(2024, 1, 1), transactions=False)
    assert "transactions" not in ctx
    assert "transactions" in supplier_report.report_context("Test Supplier", date(2024, 1, 1))
    assert "dean_moss_signature" not in ctx


def test_json_safe_dates_and_decimals():
    from decimal import Decimal
    from tps.common import json_safe
    out = json_safe({"d": date(2026, 4, 1), "n": [Decimal("1.5"), {"x": Decimal("2")}], "s": "a"})
    assert out == {"d": "2026-04-01", "n": [1.5, {"x": 2.0}], "s": "a"}
    assert all(type(v) is float for v in (out["n"][0], out["n"][1]["x"]))


def test_report_context_empty_month():
    import json
    from tps.common import json_safe
    empty = dict(get_supplier_kpis=lambda *a: {}, get_global_ranking=lambda *a: (None, 0, False),
                 get_local_rankings=lambda *a: [], get_compliance_rate=lambda *a: 0.0,
                 get_monthly_compliance_scores=lambda *a: ([], []), get_standard_carton_scores=lambda *a: ([], []),
                 get_density_scores=lambda *a: ([], []), get_associated_factories=lambda *a: [],
                 get_line_details=lambda *a: ([], EMPTY_TOTALS), get_compliance_data=lambda *a: [],
                 get_transactions=lambda *a: [])
    with patch.multiple("tps.reports.supplier_report", **empty):
        json.dumps(json_safe(supplier_report.report_context("S", date(2026, 9, 1))))


def test_json_safe_keys_and_sets():
    import json
    from decimal import Decimal
    from tps.common import json_safe
    out = json_safe({date(2026, 8, 1): Decimal("1.5"), Decimal("2"): {3, 1}, 7: "x"})
    assert out == {"2026-08-01": 1.5, "2.0": [1, 3], "7": "x"}
    assert json.loads(json.dumps(out)) == out

"""Dashboard figures must equal the report figures, on real PostgreSQL (this also
exercises GROUP BY on the `month` alias and array_agg(DISTINCT ...) as a list)."""

import pytest
from sqlalchemy import text

from tps.reports.kpi_report import pct_change
from tps.metrics.dashboard import Filters, kpi, supplier_compliance
from tps.metrics.kpi import (get_kpi_avg_lines_per_day, get_kpi_region_reflected_lines,
                             get_kpi_supplier_factory_trend)
from tps.metrics.summary import get_suppliers_below_threshold, get_top_suppliers
from tps.metrics.supplier import get_compliance_rate, get_global_ranking

from .conftest import MONTHS

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("month", MONTHS)
def test_supplier_compliance_matches_reports(test_db, month):
    d = supplier_compliance(Filters(month=month))
    with test_db.connect() as conn:
        compliant, total = conn.execute(text("""
            SELECT COUNT(*) FILTER (WHERE compliance_status = 'Compliant'), COUNT(*) FROM raw_data
            WHERE date_trunc('month', handover_date) = :m"""), {"m": month}).one()
    assert d["cards"]["compliance"] == round(compliant / total * 100, 1)
    assert d["totals"] == {"suppliers": 5, "lines": total}

    for s in d["suppliers"]:
        assert s["compliance"] == round(get_compliance_rate(s["name"], month.year, month.month), 1)
        assert s["rank"] == get_global_ranking(s["name"], month)[0]
    by_name = {s["name"]: s for s in d["suppliers"]}
    assert by_name["S_MIX"]["countries"] == ["Bangladesh", "China"]  # array_agg came back as a list
    assert by_name["S_MIX"]["region"] == "CN"  # mixed-region supplier follows the report rule
    assert d["cards"]["status"]["pending"] == 1

    assert d["cards"]["follow_up_count"] == len(get_suppliers_below_threshold(month))
    assert d["cards"]["follow_up_count"] > 0
    assert d["cards"]["top_count"] == len(get_top_suppliers(month)) == 1


@pytest.mark.parametrize("month", MONTHS)
def test_kpi_matches_reports(month):
    d = kpi(Filters(month=month))
    regions = get_kpi_region_reflected_lines(month)
    assert d["region_lines"] == regions

    avg = get_kpi_avg_lines_per_day(month)
    for k in ("bd", "cn"):
        assert d["cards"][k] == {x: avg[k][x] for x in ("lines", "working_days", "avg")}

    people = get_kpi_supplier_factory_trend(month)
    assert d["people"]["labels"] == people["labels"]
    for k in ("bd", "cn"):
        assert d["people"][k] == people[k]
    assert d["cards"]["suppliers"] == people["suppliers"][-1]
    assert d["cards"]["factories"] == people["factories"][-1]
    assert d["cards"]["lines"] == regions["bd"][-1] + regions["cn"][-1]
    # change fields: absolute counts for suppliers/factories, percent for lines
    c = d["cards"]
    if len(people["labels"]) > 1:
        assert c["suppliers_change"] == people["suppliers"][-1] - people["suppliers"][-2]
        assert c["factories_change"] == people["factories"][-1] - people["factories"][-2]
        lines = [a + b for a, b in zip(regions["bd"], regions["cn"])]
        assert c["lines_change_pct"] == pct_change(lines[-1], lines[-2])
        assert c["lines_change_pct"] is not None
    else:
        assert c["suppliers_change"] is None and c["factories_change"] is None


@pytest.mark.parametrize("month", MONTHS)
def test_contexts_match_report_functions(month):
    from tps.metrics import summary as sm
    from tps.metrics.supplier import (get_associated_factories, get_compliance_data, get_line_details,
                                      get_local_rankings, get_monthly_compliance_scores,
                                      get_supplier_kpis)
    from tps.reports.summary_excel import summary_context
    from tps.reports.supplier_report import report_context

    c = summary_context(month)
    assert c["sources"] == sm.get_summary_sources(month)
    assert c["compliance_data"] == sm.get_summary_country_compliance(month)
    assert (c["country_data"], c["chart_labels"], c["country_order"]) == sm.get_summary_country_monthly_trend(month)
    assert (c["line_details"], c["line_totals"]) == sm.get_summary_line_details(month)
    assert c["top_suppliers"] == sm.get_top_suppliers(month)
    assert c["suppliers_below"] == sm.get_suppliers_below_threshold(month)
    assert (c["all_supplier_trend"], c["month_labels"]) == sm.get_all_suppliers_trend(month)
    assert c["email_map"] == sm.get_supplier_emails_map()

    for s in supplier_compliance(Filters(month=month))["suppliers"]:
        name = s["name"]
        r = report_context(name, month)
        assert r["compliance_rate"] == get_compliance_rate(name, month.year, month.month)
        assert (r["ranking"], r["total_suppliers"], r["shared"]) == get_global_ranking(name, month)
        assert r["local_rankings"] == get_local_rankings(name, month)
        assert (r["monthly_compliance_scores"], r["monthly_compliance_labels"]) == get_monthly_compliance_scores(name, month)
        assert [(f["factory"], f["origin_countries"], f["compliance_rate"]) for f in r["associated_factories"]] == \
            [(f["factory"], f["origin_countries"], f["compliance_rate"]) for f in get_associated_factories(name, month)]
        assert r["kpis"] == get_supplier_kpis(name, month)
        assert (r["line_details"], r["line_totals"]) == get_line_details(name, month)
        assert r["compliance_data"] == get_compliance_data(name, month)

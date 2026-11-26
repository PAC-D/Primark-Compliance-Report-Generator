from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from tps.reports import kpi_report as kpi_renderer


def row(country, suppliers, factories, lines):
    return {"country": country, "suppliers": suppliers, "factories": factories, "reflected_lines": lines}


def table(label, rows):
    totals = {k: sum(r[k] for r in rows) for k in ("suppliers", "factories", "reflected_lines")}
    return {"month_label": label, "rows": rows, "totals": totals}


JUNE = table("Jun '26", [row("Bangladesh", 3, 4, 60), row("China", 2, 2, 40)])
MAY = table("May '26", [row("China", 1, 1, 50), row("Vietnam", 1, 1, 10)])
TREND = {"labels": ["May '26", "Jun '26"], "suppliers": [8, 10], "factories": [12, 15],
         "bd": {"suppliers": [3, 4], "factories": [5, 6]}, "cn": {"suppliers": [5, 6], "factories": [7, 9]}}
REGION = {"labels": ["May '26", "Jun '26"], "bd": [50, 60], "cn": [30, 40]}
AVG = {"bd": {"region": "BD", "lines": 230, "working_days": 23, "avg": 10},
       "cn": {"region": "CN", "lines": 154, "working_days": 22, "avg": 7}}


def metrics(tables, labels, trend=TREND, region=REGION):
    return patch.multiple(
        "tps.reports.kpi_report",
        get_kpi_monthly_tables=MagicMock(return_value=tables),
        get_kpi_approved_by_performance=MagicMock(return_value={
            "month_labels": labels, "rows": [{"approved_by": "Alex Doe", "lines": [5] + [3] * (len(labels) - 1)}] if labels else []}),
        get_kpi_avg_lines_per_day=MagicMock(return_value=AVG),
        get_kpi_supplier_factory_trend=MagicMock(return_value=trend),
        get_kpi_region_reflected_lines=MagicMock(return_value=region),
    )


class TestRenderKpiReport:
    def test_renders_one_document(self):
        with metrics([JUNE, MAY], ["Jun '26", "May '26"]):
            html = kpi_renderer.render_kpi_report(date(2026, 6, 1))
        assert html.count("<!DOCTYPE html>") == 1
        for text in ("Transit Packaging System (TPS)", "KPI Report", "June 2026", "Monthly Summary",
                     "Individual Performance", "Average lines processed per day", "Alex Doe", "chartTrend", "chartRegion"):
            assert text in html
        assert "page-header" not in html  # logos and page numbers come from the PDF header/footer

    def test_each_table_month_adds_a_column_per_group(self):
        june_last_year = table("Jun '25", [row("China", 1, 1, 5)])
        with metrics([JUNE, MAY, june_last_year], ["Jun '26", "May '26", "Jun '25"]):
            html = kpi_renderer.render_kpi_report(date(2026, 6, 1))
        assert html.count(">Jun &#39;25</th>") == 3 + 1  # suppliers, factories, lines + Individual Performance

    def test_hides_monthly_summary_without_tables(self):
        with metrics([], []):
            html = kpi_renderer.render_kpi_report(date(2026, 6, 1))
        assert "Monthly Summary" not in html
        assert "No approved-by data available." in html

    def test_raises_when_no_data(self):
        with patch.multiple(
            "tps.reports.kpi_report",
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


class TestHeadline:
    def test_this_month_against_the_month_before(self):
        h = kpi_renderer.headline(TREND, REGION)
        assert h["previous_label"] == "May '26"
        assert h["lines"] == {"now": 100, "before": 80, "change": 25}
        assert h["suppliers"] == {"now": 10, "before": 8, "change": 25}
        assert h["factories"] == {"now": 15, "before": 12, "change": 25}
        assert (h["bd_lines"], h["cn_lines"], h["bd_share"], h["cn_share"]) == (60, 40, 60, 40)

    def test_rounds_falls_to_whole_percent(self):
        h = kpi_renderer.headline({**TREND, "suppliers": [127, 108]}, REGION)
        assert h["suppliers"]["change"] == -15

    def test_no_previous_month(self):
        trend = {"labels": ["Jun '26"], "suppliers": [10], "factories": [15]}
        h = kpi_renderer.headline(trend, {"labels": ["Jun '26"], "bd": [60], "cn": [40]})
        assert h["previous_label"] is None
        assert h["lines"] == {"now": 100, "before": None, "change": None}

    def test_previous_month_with_nothing_has_no_change(self):
        h = kpi_renderer.headline({**TREND, "suppliers": [0, 10]}, REGION)
        assert h["suppliers"] == {"now": 10, "before": 0, "change": None}

    def test_no_lines_gives_zero_shares(self):
        h = kpi_renderer.headline(TREND, {"labels": REGION["labels"], "bd": [0, 0], "cn": [0, 0]})
        assert (h["bd_share"], h["cn_share"]) == (0, 0)


class TestMonthComparison:
    def test_one_row_per_country_across_months(self):
        rows = kpi_renderer.month_comparison([JUNE, MAY])
        assert [r["country"] for r in rows] == ["Bangladesh", "China", "Vietnam"]
        assert [r["region"] for r in rows] == ["bd", "cn", "cn"]
        assert rows[0]["cells"] == [JUNE["rows"][0], None]
        assert rows[2]["cells"] == [None, MAY["rows"][1]]

    def test_share_of_the_first_months_lines(self):
        rows = kpi_renderer.month_comparison([JUNE, MAY])
        assert [r["share"] for r in rows] == [60, 40, 0]

    def test_no_tables(self):
        assert kpi_renderer.month_comparison([]) == []

    def test_no_lines_gives_zero_share(self):
        empty = table("Jun '26", [row("China", 1, 1, 0)])
        assert kpi_renderer.month_comparison([empty])[0]["share"] == 0


def test_kpi_report_is_sharp():
    import re
    with metrics([JUNE, MAY], ["Jun '26", "May '26"]):
        html = kpi_renderer.render_kpi_report(date(2026, 6, 1))
    assert not re.search(r"box-shadow:\s*[-\d.]+(?:px)?\s+[-\d.]+(?:px)?\s+[1-9]", html)
    assert "devicePixelRatio:3" in html

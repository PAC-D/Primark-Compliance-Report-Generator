"""Monthly KPI report across all suppliers."""

from datetime import date

from tps.common import get_report_month
from tps.metrics.kpi import (
    classify_region,
    get_kpi_approved_by_performance,
    get_kpi_avg_lines_per_day,
    get_kpi_monthly_tables,
    get_kpi_region_reflected_lines,
    get_kpi_supplier_factory_trend,
)
from tps.reports.html import render


def pct_change(now: int, before: int | None) -> int | None:
    """Whole-percent change, or None when there is nothing to compare with."""
    return round((now - before) / before * 100) if before else None


def headline(trend: dict, region_lines: dict) -> dict:
    """This month's totals and the month before's, from the chart series (their last point is the report month)."""
    lines = [bd + cn for bd, cn in zip(region_lines["bd"], region_lines["cn"])]

    def now_and_before(series):
        before = series[-2] if len(series) > 1 else None
        return {"now": series[-1], "before": before, "change": pct_change(series[-1], before)}

    bd, cn = region_lines["bd"][-1], region_lines["cn"][-1]
    bd_share = round(bd / (bd + cn) * 100) if bd + cn else 0
    return {
        "previous_label": trend["labels"][-2] if len(trend["labels"]) > 1 else None,
        "lines": now_and_before(lines),
        "suppliers": now_and_before(trend["suppliers"]),
        "factories": now_and_before(trend["factories"]),
        "bd_lines": bd,
        "cn_lines": cn,
        "bd_share": bd_share,
        "cn_share": 100 - bd_share if bd + cn else 0,
    }


def month_comparison(monthly_tables: list[dict]) -> list[dict]:
    """One row per country across the table months: its region ("bd"/"cn"), one cell per month
    (None where the country had no lines) and its share of the first month's reflected lines."""
    by_month = [{r["country"]: r for r in t["rows"]} for t in monthly_tables]
    total = monthly_tables[0]["totals"]["reflected_lines"] if monthly_tables else 0
    rows = []
    for country in sorted({c for month in by_month for c in month}):
        cells = [month.get(country) for month in by_month]
        lines = cells[0]["reflected_lines"] if cells[0] else 0
        rows.append({"country": country, "region": classify_region(country).lower(), "cells": cells,
                     "share": round(lines / total * 100) if total else 0})
    return rows


def render_kpi_report(report_month: date | None = None) -> str:
    if report_month is None:
        report_month = get_report_month()

    monthly_tables = get_kpi_monthly_tables(report_month)
    performance = get_kpi_approved_by_performance(report_month)
    avg_per_day = get_kpi_avg_lines_per_day(report_month)

    has_data = (
        bool(monthly_tables)
        or bool(performance["rows"])
        or avg_per_day["bd"]["lines"] > 0
        or avg_per_day["cn"]["lines"] > 0
    )
    if not has_data:
        raise ValueError("No data available for the KPI report in the selected month.")

    trend = get_kpi_supplier_factory_trend(report_month)
    region_lines = get_kpi_region_reflected_lines(report_month)
    return render(
        "kpi_report.html.j2",
        month_name=report_month.strftime("%B"),
        year=report_month.year,
        headline=headline(trend, region_lines),
        avg_per_day=avg_per_day,
        monthly_tables=monthly_tables,
        months=[t["month_label"] for t in monthly_tables],
        comparison=month_comparison(monthly_tables),
        performance=performance,
        performance_max=max((v for r in performance["rows"] for v in r["lines"]), default=0),
        trend=trend,
        region_lines=region_lines,
    )

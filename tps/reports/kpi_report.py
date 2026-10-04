"""Monthly KPI report across all suppliers."""

from datetime import date, datetime

from tps.common import get_report_month
from tps.metrics.kpi import (
    get_kpi_approved_by_performance,
    get_kpi_avg_lines_per_day,
    get_kpi_monthly_tables,
    get_kpi_region_reflected_lines,
    get_kpi_supplier_factory_trend,
)
from tps.reports.html import ALLPORT_LOGO, PRIMARK_LOGO, render


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

    return render(
        "kpi_report.html.j2",
        month_name=report_month.strftime("%B"),
        year=report_month.year,
        release_date=datetime.now().strftime("%d %B %Y"),
        monthly_tables=monthly_tables,
        performance=performance,
        avg_per_day=avg_per_day,
        trend=get_kpi_supplier_factory_trend(report_month),
        region_lines=get_kpi_region_reflected_lines(report_month),
        primark_logo=PRIMARK_LOGO,
        allport_logo=ALLPORT_LOGO,
    )

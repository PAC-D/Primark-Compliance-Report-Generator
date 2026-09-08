import base64
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from kpi_metrics import (
    get_kpi_approved_by_performance,
    get_kpi_avg_lines_per_day,
    get_kpi_monthly_tables,
    get_kpi_region_reflected_lines,
    get_kpi_supplier_factory_trend,
)
from metrics import get_report_month

ASSETS_PATH = Path(__file__).parent / "assets"


def _load_logo(name: str) -> str:
    with open(ASSETS_PATH / name, "rb") as f:
        return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"


PRIMARK_LOGO = _load_logo("Primark-logo.png")
ALLPORT_LOGO = _load_logo("allport-pacd-logo.png")


def render_kpi_report(report_month: date | None = None) -> str:
    if report_month is None:
        report_month = get_report_month()

    monthly_tables = get_kpi_monthly_tables(report_month)
    performance = get_kpi_approved_by_performance(report_month)
    avg_per_day = get_kpi_avg_lines_per_day(report_month)
    trend = get_kpi_supplier_factory_trend(report_month)
    region_lines = get_kpi_region_reflected_lines(report_month)

    has_data = (
        bool(monthly_tables)
        or bool(performance["rows"])
        or avg_per_day["bd"]["lines"] > 0
        or avg_per_day["cn"]["lines"] > 0
    )
    if not has_data:
        raise ValueError("No data available for the KPI report in the selected month.")

    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"])
    )
    template = env.get_template("kpi_report.html.j2")

    context = {
        "month_name": report_month.strftime("%B"),
        "year": report_month.year,
        "release_date": datetime.now().strftime("%d %B %Y"),
        "monthly_tables": monthly_tables,
        "performance": performance,
        "avg_per_day": avg_per_day,
        "trend": trend,
        "region_lines": region_lines,
        "primark_logo": PRIMARK_LOGO,
        "allport_logo": ALLPORT_LOGO,
    }
    return template.render(**context)

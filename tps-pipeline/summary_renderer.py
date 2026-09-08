from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from datetime import date, datetime
import base64

from metrics import (
    get_report_month,
    get_summary_sources,
    get_summary_country_compliance,
    get_summary_country_volume,
    get_summary_country_monthly_trend,
    get_summary_line_details,
    get_top_suppliers
)

CONFIG_PATH = Path(__file__).parent / "config.yaml"
ASSETS_PATH = Path(__file__).parent / "assets"

def _load_logo(name: str) -> str:
    with open(ASSETS_PATH / name, "rb") as f:
        return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"

PRIMARK_LOGO = _load_logo("Primark-logo.png")
ALLPORT_LOGO = _load_logo("allport-pacd-logo.png")


def _get_working_days(report_month: date) -> str:
    year, month = report_month.year, report_month.month
    import calendar
    _, num_days = calendar.monthrange(year, month)
    fridays_saturdays = sum(
        1 for day in range(1, num_days + 1)
        if calendar.weekday(year, month, day) in (calendar.FRIDAY, calendar.SATURDAY)
    )
    working = num_days - fridays_saturdays
    return f"{working}/{num_days}"


def render_summary_report(report_month: date | None = None) -> str:
    if report_month is None:
        report_month = get_report_month()

    sources = get_summary_sources(report_month)
    compliance_data = get_summary_country_compliance(report_month)
    volume_data = get_summary_country_volume(report_month)
    country_data, chart_labels, country_order = get_summary_country_monthly_trend(report_month)
    line_details, line_totals = get_summary_line_details(report_month)
    top_suppliers = get_top_suppliers(report_month)

    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"])
    )
    template = env.get_template("summary_report.html.j2")

    context = {
        "month_name": report_month.strftime("%B"),
        "year": report_month.year,
        "release_date": datetime.now().strftime("%d %B %Y"),
        "sources": sources,
        "compliance_data": compliance_data,
        "line_details": line_details,
        "line_totals": line_totals,
        "volume_data": volume_data,
        "country_data": country_data,
        "chart_labels": chart_labels,
        "country_order": country_order,
        "primark_logo": PRIMARK_LOGO,
        "allport_logo": ALLPORT_LOGO,
        "working_days": _get_working_days(report_month),
        "top_suppliers": top_suppliers,
    }

    return template.render(**context)
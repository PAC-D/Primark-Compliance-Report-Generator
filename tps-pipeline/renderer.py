from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
import yaml
from datetime import datetime, date
from collections import defaultdict
import functools

from metrics import (
    get_report_month, get_compliance_rate, get_monthly_compliance_scores,
    get_standard_carton_scores, get_density_scores, get_global_ranking,
    get_local_rankings, get_supplier_kpis,
    get_associated_factories, get_line_details, get_compliance_data,
    get_transactions, get_volume_scores
)


CONFIG_PATH = Path(__file__).parent / "config.yaml"
TABLE_COLUMNS_PATH = Path(__file__).parent / "config" / "table_columns.yaml"
ASSETS_PATH = Path(__file__).parent / "assets"

import base64

def _load_logo(name: str) -> str:
    with open(ASSETS_PATH / name, "rb") as f:
        return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"

def _load_signature(name: str) -> str:
    with open(ASSETS_PATH / name, "rb") as f:
        return f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"

PRIMARK_LOGO = _load_logo("Primark-logo.png")
ALLPORT_LOGO = _load_logo("allport-pacd-logo.png")
DEAN_MOSS_SIGNATURE = _load_signature("DeanMoss.jpg")

CORRUGATED_ADD_LENGTH = 6
CORRUGATED_ADD_WIDTH = 4
CORRUGATED_DIVISOR = 10000


def make_landscape_header_footer(primark_logo: str, allport_logo: str, month_name: str = "", year: int = 0) -> tuple[str, str]:
    header_html = f'''<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 16px;border-bottom:4px solid #e31837;">
  <img src="{primark_logo}" style="height:25px;width:auto;" alt="Primark">
  <img src="{allport_logo}" style="height:28px;width:auto;" alt="Allport">
</div>'''
    footer_html = f'''<div style="display:flex;justify-content:space-between;padding:6px 16px;border-top:1px solid #e5e7eb;font-size:8px;color:#6b7280;">
  <span>Generated: {datetime.now().strftime("%d %B %Y")}</span>
  <span>TPS Transaction Report</span>
</div>'''
    return header_html, footer_html


@functools.lru_cache(maxsize=1)
def _load_table_columns():
    with open(TABLE_COLUMNS_PATH) as f:
        return yaml.safe_load(f)


def get_renderer_config() -> dict:
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    return {
        "database": config.get("database", {}),
        "paths": config.get("paths", {}),
        "app": config.get("app", {})
    }


def calculate_corrugated_sqm(factory_transactions: list) -> float:
    total_sqm = 0.0
    for txn in factory_transactions:
        length = txn.get("carton_length_mm")
        width = txn.get("carton_width_mm")
        height = txn.get("carton_height_mm")

        if length is None or width is None or height is None:
            continue

        L = length / 10
        W = width / 10
        H = height / 10
        sqm = ((L + CORRUGATED_ADD_LENGTH) * (W + H + CORRUGATED_ADD_WIDTH) * 2) / CORRUGATED_DIVISOR
        total_sqm += sqm

    return round(total_sqm)


def _make_gauge_arc(rate: float) -> dict:
    """Compute SVG arc path for a half-circle gauge. rate is 0-100."""
    import math
    rate = max(0, min(100, rate))
    # Half circle arc length for r=90: π * 90 ≈ 282.7
    dasharray = round(rate * 2.827, 1)
    return {
        "rate": rate,
        "color": "#059669" if rate >= 70 else "#f59e0b" if rate >= 40 else "#e31837",
        "dasharray": f"{dasharray} 283",
    }


def render_report(supplier: str, report_month: date | None = None) -> tuple[str, str | None]:
    if report_month is None:
        report_month = get_report_month()

    table_columns = _load_table_columns()

    kpis = get_supplier_kpis(supplier, report_month)
    ranking, total, shared = get_global_ranking(supplier, report_month)
    local_rankings = get_local_rankings(supplier, report_month)

    compliance_rate = get_compliance_rate(supplier, report_month.year, report_month.month)
    monthly_compliance_scores, monthly_compliance_labels = get_monthly_compliance_scores(supplier, report_month=report_month)
    standard_carton_scores, standard_carton_labels = get_standard_carton_scores(supplier, report_month=report_month)
    density_scores, density_labels = get_density_scores(supplier, report_month=report_month)
    volume_scores, volume_labels = get_volume_scores(supplier, report_month=report_month)
    associated_factories = get_associated_factories(supplier, report_month)
    line_details, line_totals = get_line_details(supplier, report_month)
    compliance_data = get_compliance_data(supplier, report_month)
    transactions = get_transactions(supplier, report_month)
    for txn in transactions:
        if txn.get('updated_date'):
            txn['updated_date'] = txn['updated_date'].strftime('%d %b %Y')
        if txn.get('approved_date'):
            txn['approved_date'] = txn['approved_date'].strftime('%d %b %Y')
        if txn.get('handover_date'):
            txn['handover_date'] = txn['handover_date'].strftime('%d %b %Y')

    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"])
    )
    env.globals['enumerate'] = enumerate
    template = env.get_template("report.html.j2")

    gauge = _make_gauge_arc(compliance_rate)

    context = {
        "supplier_name": supplier,
        "month_name": report_month.strftime("%B"),
        "month_num": report_month.month,
        "year": report_month.year,
        "release_date": datetime.now().strftime("%d %B %Y"),
        "kpis": kpis,
        "ranking": ranking,
        "total_suppliers": total,
        "shared": shared,
        "local_rankings": local_rankings,
        "multi_country": len(local_rankings) > 1,
        "long_supplier_name": len(supplier) > 30,
        "compliance_rate": compliance_rate,
        "gauge": gauge,
        "monthly_compliance_scores": monthly_compliance_scores,
        "standard_carton_scores": standard_carton_scores,
        "density_scores": density_scores,
        "volume_scores": volume_scores,
        "monthly_compliance_labels": monthly_compliance_labels,
        "standard_carton_labels": standard_carton_labels,
        "density_labels": density_labels,
        "volume_labels": volume_labels,
        "associated_factories": associated_factories,
        "line_details": line_details,
        "line_totals": line_totals,
        "compliance_data": compliance_data,
        "transactions": transactions,
        "table_columns": table_columns,
        "primark_logo": PRIMARK_LOGO,
        "allport_logo": ALLPORT_LOGO,
        "dean_moss_signature": DEAN_MOSS_SIGNATURE,
    }

    full_html = template.render(**context)

    marker = '<div class="page-break-landscape"></div>'
    if marker not in full_html:
        return full_html, None

    parts = full_html.split(marker)
    portrait_html = parts[0]
    landscape_body = parts[1]

    landscape_html = f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>TPS Report</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ width: 100%; height: auto; background: white; font-family: Inter, -apple-system, sans-serif; }}
    @page {{ size: 297mm 210mm; margin: 20mm 15mm 15mm 15mm; }}
    body {{ display: block; }}
    .landscape-page-header, .landscape-footer {{ display: none; }}
    .landscape-table {{ width: 100%; border-collapse: collapse; font-size: 9px; }}
    .landscape-table th {{ background:#1B2838; color:white; font-weight:600; text-transform:uppercase; font-size:8px; padding:4px 6px; text-align:left; }}
    .landscape-table td {{ padding:3px 6px; border-bottom:1px solid #e5e7eb; color:#374151; }}
    .landscape-table tbody tr:nth-child(even) {{ background:#f9fafb; }}
    .status-badge {{ display:inline-block; padding:1px 4px; border-radius:2px; font-size:7px; font-weight:700; text-transform:uppercase; }}
    .status-badge.success {{ background:#d1fae5; color:#059669; }}
    .status-badge.danger {{ background:#fee2e2; color:#dc2626; }}
    .status-badge.warning {{ background:#fef3c7; color:#ea580c; }}
    .text-right {{ text-align:right; }}
    .brand-img-primark {{ height: 25px; width: auto; }}
    .brand-img-allport {{ height: 28px; width: auto; }}
  </style>
</head>
<body>
{landscape_body}
</body>
</html>'''

    return portrait_html, landscape_html

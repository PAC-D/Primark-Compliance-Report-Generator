"""Per-supplier compliance report: portrait summary pages + landscape transaction list."""

from datetime import date, datetime

from tps.common import get_report_month
from tps.metrics.supplier import (
    get_associated_factories,
    get_compliance_data,
    get_compliance_rate,
    get_density_scores,
    get_global_ranking,
    get_line_details,
    get_local_rankings,
    get_monthly_compliance_scores,
    get_standard_carton_scores,
    get_supplier_kpis,
    get_transactions,
)
from tps.reports.html import ALLPORT_LOGO, DEAN_MOSS_SIGNATURE, PRIMARK_LOGO, render

# The template marks where the portrait pages end and the landscape pages begin.
LANDSCAPE_MARKER = '<div class="page-break-landscape"></div>'


def _make_gauge_arc(rate: float) -> dict:
    """SVG stroke settings for the half-circle gauge. rate is 0-100."""
    rate = max(0, min(100, rate))
    # Half circle arc length for r=90: pi * 90 ~= 282.7
    dasharray = round(rate * 2.827, 1)
    return {
        "rate": rate,
        "color": "#059669" if rate >= 70 else "#f59e0b" if rate >= 40 else "#e31837",
        "dasharray": f"{dasharray} 283",
    }


def render_report(supplier: str, report_month: date | None = None) -> tuple[str, str | None]:
    """Returns (portrait_html, landscape_html); landscape is None when the
    template has no landscape section."""
    if report_month is None:
        report_month = get_report_month()

    ranking, total, shared = get_global_ranking(supplier, report_month)
    local_rankings = get_local_rankings(supplier, report_month)
    compliance_rate = get_compliance_rate(supplier, report_month.year, report_month.month)
    monthly_compliance_scores, monthly_compliance_labels = get_monthly_compliance_scores(supplier, report_month)
    standard_carton_scores, standard_carton_labels = get_standard_carton_scores(supplier, report_month)
    density_scores, density_labels = get_density_scores(supplier, report_month)
    line_details, line_totals = get_line_details(supplier, report_month)

    transactions = get_transactions(supplier, report_month)
    for txn in transactions:
        for key in ("updated_date", "approved_date", "handover_date"):
            if txn.get(key):
                txn[key] = txn[key].strftime("%d %b %Y")

    full_html = render(
        "report.html.j2",
        supplier_name=supplier,
        month_name=report_month.strftime("%B"),
        year=report_month.year,
        release_date=datetime.now().strftime("%d %B %Y"),
        kpis=get_supplier_kpis(supplier, report_month),
        ranking=ranking,
        total_suppliers=total,
        shared=shared,
        local_rankings=local_rankings,
        multi_country=len(local_rankings) > 1,
        long_supplier_name=len(supplier) > 30,
        compliance_rate=compliance_rate,
        gauge=_make_gauge_arc(compliance_rate),
        monthly_compliance_scores=monthly_compliance_scores,
        monthly_compliance_labels=monthly_compliance_labels,
        standard_carton_scores=standard_carton_scores,
        standard_carton_labels=standard_carton_labels,
        density_scores=density_scores,
        density_labels=density_labels,
        associated_factories=get_associated_factories(supplier, report_month),
        line_details=line_details,
        line_totals=line_totals,
        compliance_data=get_compliance_data(supplier, report_month),
        transactions=transactions,
        primark_logo=PRIMARK_LOGO,
        allport_logo=ALLPORT_LOGO,
        dean_moss_signature=DEAN_MOSS_SIGNATURE,
    )

    if LANDSCAPE_MARKER not in full_html:
        return full_html, None

    portrait_html, landscape_body = full_html.split(LANDSCAPE_MARKER)[:2]

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

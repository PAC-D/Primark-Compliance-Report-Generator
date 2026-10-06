"""Per-supplier compliance report: one HTML document, A4 portrait summary pages
followed by A4 landscape transaction pages."""

from collections import Counter
from datetime import date

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
from tps.reports.html import DEAN_MOSS_SIGNATURE, render


def rate_band(rate: float) -> str:
    """'high' (70% and up), 'mid' (40% and up) or 'low'; the template colours by band."""
    return "high" if rate >= 70 else "mid" if rate >= 40 else "low"


def render_report(supplier: str, report_month: date | None = None) -> str:
    if report_month is None:
        report_month = get_report_month()

    ranking, total, shared = get_global_ranking(supplier, report_month)
    compliance_rate = get_compliance_rate(supplier, report_month.year, report_month.month)
    monthly_compliance_scores, monthly_compliance_labels = get_monthly_compliance_scores(supplier, report_month)
    standard_carton_scores, standard_carton_labels = get_standard_carton_scores(supplier, report_month)
    density_scores, density_labels = get_density_scores(supplier, report_month)
    line_details, line_totals = get_line_details(supplier, report_month)

    factories = get_associated_factories(supplier, report_month)
    for f in factories:
        f["band"] = rate_band(f["compliance_rate"])

    transactions = get_transactions(supplier, report_month)
    for txn in transactions:
        for key in ("updated_date", "approved_date", "handover_date"):
            if txn.get(key):
                txn[key] = txn[key].strftime("%d %b %Y")

    return render(
        "report.html.j2",
        supplier_name=supplier,
        month_name=report_month.strftime("%B"),
        year=report_month.year,
        kpis=get_supplier_kpis(supplier, report_month),
        ranking=ranking,
        total_suppliers=total,
        shared=shared,
        local_rankings=get_local_rankings(supplier, report_month),
        compliance_rate=compliance_rate,
        band=rate_band(compliance_rate),
        factory_bands=Counter(f["band"] for f in factories),
        monthly_compliance_scores=monthly_compliance_scores,
        monthly_compliance_labels=monthly_compliance_labels,
        standard_carton_scores=standard_carton_scores,
        standard_carton_labels=standard_carton_labels,
        density_scores=density_scores,
        density_labels=density_labels,
        associated_factories=factories,
        line_details=line_details,
        line_totals=line_totals,
        compliance_data=get_compliance_data(supplier, report_month),
        transactions=transactions,
        dean_moss_signature=DEAN_MOSS_SIGNATURE,
    )

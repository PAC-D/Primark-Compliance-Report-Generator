"""Reconstructs renderer inputs from the reference workbook.

The reference (`fixtures/reference_july_2026.xlsx`) is the pipeline's own July
2026 output after being polished by hand in Excel. Its *values* are unchanged
from what the pipeline produced, so reading them back gives us the exact inputs
the renderer was called with - letting the layout tests drive the real builders
without a database.
"""

from datetime import date
from pathlib import Path

from openpyxl import load_workbook

REFERENCE_PATH = Path(__file__).parent / "fixtures" / "reference_july_2026.xlsx"
REPORT_MONTH = date(2026, 7, 1)
MONTH_NAME = "July"
YEAR = 2026


def load_reference():
    return load_workbook(REFERENCE_PATH)


def _pct(value):
    """Reference stores fractions; the renderer takes percentages (0-100)."""
    if value is None or value == "":
        return None
    return round(float(value) * 100, 10)


def _month_label(d):
    return f"{d.strftime('%b')} '{d.strftime('%y')}"


def sources(wb):
    ws = wb["Summary"]
    return {"total_suppliers": ws["A5"].value, "total_factories": ws["B5"].value}


def compliance_data(wb):
    ws = wb["Summary"]
    rows = []
    for row in range(9, 18):
        rows.append(
            {"country": ws.cell(row=row, column=1).value,
             "compliance_rate": _pct(ws.cell(row=row, column=2).value)}
        )
    return rows


def country_monthly_trend(wb):
    """Returns (country_data, chart_labels, country_order).

    The reference's final month header reads "Jul '27" - a slip made while
    editing by hand. The label is regenerated from the report month here, so the
    fixture carries the correct "Jul '26".
    """
    ws = wb["Summary"]
    chart_labels = [ws.cell(row=28, column=col).value for col in range(5, 12)]
    chart_labels[-1] = _month_label(REPORT_MONTH)

    country_order = []
    country_data = {}
    for row in range(29, 38):
        country = ws.cell(row=row, column=4).value
        country_order.append(country)
        country_data[country] = [
            _pct(ws.cell(row=row, column=col).value) for col in range(5, 12)
        ]
    return country_data, chart_labels, country_order


def line_details(wb):
    ws = wb["Visibility"]
    details = []
    for row in range(3, 12):
        details.append({
            "country": ws.cell(row=row, column=1).value,
            "dest_po_count": ws.cell(row=row, column=2).value,
            "reflected_lines": ws.cell(row=row, column=3).value,
            "approved": ws.cell(row=row, column=4).value,
            "rejected": ws.cell(row=row, column=5).value,
        })

    totals = {
        key: sum(d[key] for d in details)
        for key in ("dest_po_count", "reflected_lines", "approved", "rejected")
    }
    return details, totals


def top_suppliers(wb):
    ws = wb["Top Performers"]
    suppliers = []
    for row in range(3, ws.max_row + 1):
        if ws.cell(row=row, column=3).value is None:
            continue
        suppliers.append({
            "sl": ws.cell(row=row, column=1).value,
            "origin_countries": ws.cell(row=row, column=2).value,
            "supplier": ws.cell(row=row, column=3).value,
            "factory_count": ws.cell(row=row, column=4).value,
            "dest_po_count": ws.cell(row=row, column=5).value,
            "reflected_lines": ws.cell(row=row, column=6).value,
            "compliance_rate": _pct(ws.cell(row=row, column=7).value),
        })
    return suppliers


def suppliers_below(wb):
    ws = wb["Follow-Up Required"]
    suppliers = []
    for row in range(3, ws.max_row + 1):
        if ws.cell(row=row, column=3).value is None:
            continue
        suppliers.append({
            "sl": ws.cell(row=row, column=1).value,
            "origin_country": ws.cell(row=row, column=2).value,
            "supplier": ws.cell(row=row, column=3).value,
            "factory_count": ws.cell(row=row, column=4).value,
            "dest_po_count": ws.cell(row=row, column=5).value,
            "reflected_lines": ws.cell(row=row, column=6).value,
            "avg_3month": _pct(ws.cell(row=row, column=7).value),
            "month_label": f"{MONTH_NAME} {YEAR}",
        })
    return suppliers


def email_map(wb):
    ws = wb["Follow-Up Required"]
    mapping = {}
    for row in range(3, ws.max_row + 1):
        supplier = ws.cell(row=row, column=3).value
        if supplier is None:
            continue
        mapping[supplier.strip().lower()] = ws.cell(row=row, column=8).value or ""
    return mapping


def supplier_trend(wb):
    """Returns (all_supplier_trend, month_labels) for the Yearly sheet."""
    ws = wb["Yearly Performance"]
    month_labels = [ws.cell(row=7, column=col).value for col in range(3, 10)]

    trend = []
    for row in range(8, ws.max_row + 1):
        supplier = ws.cell(row=row, column=2).value
        if supplier is None:
            continue
        trend.append({
            "supplier": supplier,
            "rates": [_pct(ws.cell(row=row, column=col).value) for col in range(3, 10)],
        })
    return trend, month_labels


def all_inputs(wb=None):
    wb = wb or load_reference()
    country_data, chart_labels, country_order = country_monthly_trend(wb)
    details, totals = line_details(wb)
    trend, month_labels = supplier_trend(wb)
    return {
        "sources": sources(wb),
        "compliance_data": compliance_data(wb),
        "country_data": country_data,
        "chart_labels": chart_labels,
        "country_order": country_order,
        "line_details": details,
        "line_totals": totals,
        "top_suppliers": top_suppliers(wb),
        "suppliers_below": suppliers_below(wb),
        "email_map": email_map(wb),
        "all_supplier_trend": trend,
        "month_labels": month_labels,
    }

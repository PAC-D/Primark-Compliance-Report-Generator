"""The summary workbook.

Content: the builders, fed the inputs read back from the hand-checked July 2026
reference workbook, must produce the same table contents. Skipped when the
reference (confidential, not in git) is absent.

Presentation: checked on a small sample, so it always runs.
"""

import pytest
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from tps.reports.summary_excel import (
    TABLE_STYLE,
    _build_follow_up_required_sheet,
    _build_summary_sheet,
    _build_top_performers_sheet,
    _build_visibility_sheet,
    _build_yearly_performance_sheet,
)

from . import reference_data

SHEETS = ["Summary", "Visibility", "Top Performers", "Follow-Up Required", "Yearly Performance"]

SAMPLE = {
    "sources": {"total_suppliers": 108, "total_factories": 342},
    "compliance_data": [{"country": "Bangladesh", "compliance_rate": 76.0},
                        {"country": "China", "compliance_rate": 75.0}],
    "country_data": {"China": [77.0, None, 75.0], "Bangladesh": [66.0, 73.0, 76.0]},
    "chart_labels": ["Jul '26", "Aug '26", "Sep '26"],
    "country_order": ["China", "Bangladesh"],
    "line_details": [{"country": "China", "dest_po_count": 1116, "reflected_lines": 3332,
                      "approved": 2537, "rejected": 204}],
    "line_totals": {"dest_po_count": 1116, "reflected_lines": 3332, "approved": 2537, "rejected": 204},
    "top_suppliers": [{"sl": 1, "origin_countries": "China", "supplier": "ACME", "factory_count": 2,
                       "dest_po_count": 5, "reflected_lines": 50, "compliance_rate": 100.0}],
    # A row shaped like get_suppliers_below_threshold() returns; the name has a stray trailing space.
    "suppliers_below": [{"sl": 1, "origin_country": "Turkey", "supplier": "ACME TEXTILES ",
                         "factory_count": 2, "dest_po_count": 33, "reflected_lines": 143, "avg_3month": 12.5}],
    "email_map": {"acme textiles": "a@x.com, b@x.com"},
    "all_supplier_trend": [{"supplier": "ACME", "rates": [100.0, None, 35.0]}],
    "month_labels": ["Jul '26", "Aug '26", "Sep '26"],
}
WORKING_DAYS = (21, 30)  # working days (Monday to Friday), days in the month


def build(inputs, month_name, year, working_days=WORKING_DAYS):
    wb = Workbook()
    wb.remove(wb.active)
    _build_summary_sheet(wb, inputs["sources"], inputs["compliance_data"], inputs["country_data"],
                         inputs["chart_labels"], inputs["country_order"], month_name, year, working_days)
    _build_visibility_sheet(wb, inputs["line_details"], inputs["line_totals"], month_name, year)
    _build_top_performers_sheet(wb, inputs["top_suppliers"], month_name, year)
    _build_follow_up_required_sheet(wb, inputs["suppliers_below"], inputs["email_map"], f"{month_name} {year}")
    _build_yearly_performance_sheet(wb, inputs["all_supplier_trend"], inputs["month_labels"], year)
    return wb


@pytest.fixture(scope="module")
def wb():
    return build(SAMPLE, "September", 2026)


# --- Presentation --------------------------------------------------------------

def test_sheet_order(wb):
    assert wb.sheetnames == SHEETS


@pytest.mark.parametrize("sheet", SHEETS)
def test_every_sheet_has_a_title_and_subtitle_and_no_gridlines(wb, sheet):
    ws = wb[sheet]
    assert ws["B2"].value and ws["B3"].value
    assert ws.sheet_view.showGridLines is False


def test_every_table_uses_the_style_the_workbook_defines(wb):
    assert [s.name for s in wb._table_styles.tableStyle] == [TABLE_STYLE]
    tables = [t for ws in wb for t in ws.tables.values()]
    assert {t.displayName for t in tables} == {"Table2", "Table3", "Table6", "Table8", "Table9"}
    assert all(t.tableStyleInfo.name == TABLE_STYLE for t in tables)


TILES = ["B7:C7", "D7:G7", "H7:K7", "L7:O7"]  # Suppliers, Factories, Average compliance, Working days


def test_summary_tiles_show_sources_average_and_working_days(wb):
    ws = wb["Summary"]
    assert [ws[t.split(":")[0]].value for t in TILES] == [108, 342, "=C14", 21]
    assert ws["C14"].value == "=SUBTOTAL(101,Table3[Compliance Score])"  # Table3's Average row
    assert ws["L6"].value == "WORKING DAYS"
    assert ws["L7"].number_format == '0" / 30"'  # September: 21 working days of 30
    assert set(TILES) <= {str(r) for r in ws.merged_cells.ranges}


def test_summary_tiles_are_the_same_width(wb):
    ws = wb["Summary"]
    widths = []
    for tile in TILES:
        first, last = (ws[ref].column for ref in tile.split(":"))
        widths.append(sum(ws.column_dimensions[get_column_letter(c)].width for c in range(first, last + 1)))
    assert max(widths) - min(widths) <= 2, widths


def test_summary_has_no_volume_label(wb):
    texts = [str(c.value) for row in wb["Summary"].iter_rows() for c in row if c.value is not None]
    assert not any("volume" in t.lower() for t in texts)


def test_summary_without_working_days_leaves_the_tile_out():
    no_days = build(SAMPLE, "September", 2026, working_days=None)
    assert no_days["Summary"]["L6"].value is None


def test_trend_month_without_shipments_stays_blank(wb):
    ws = wb["Summary"]
    china = next(r for r in range(12, 14) if ws.cell(row=r, column=5).value == "China")
    assert [ws.cell(row=china, column=c).value for c in (6, 7, 8)] == [0.77, None, 0.75]


def test_follow_up_title_carries_the_report_month(wb):
    ws = wb["Follow-Up Required"]
    assert ws["B2"].value == "Follow-Up Required"
    assert ws["B3"].value == "Avg. Compliance <40% – Last 3 Months · September 2026"


def test_follow_up_emails_come_from_the_email_map_as_mail_links(wb):
    cell = wb["Follow-Up Required"]["I7"]
    assert cell.value == "a@x.com, b@x.com"
    assert cell.hyperlink.target == "mailto:a@x.com,b@x.com"


def test_yearly_blank_months_stay_blank_and_unshaded(wb):
    ws = wb["Yearly Performance"]
    assert [ws.cell(row=8, column=c).value for c in (4, 5, 6)] == [1.0, None, 0.35]
    assert ws["G8"].value == '=IFERROR(AVERAGE(D8:F8),"")'
    rules = [rule for cf in ws.conditional_formatting for rule in cf.rules]
    assert rules and all("ISNUMBER(D8)" in rule.formula[0] for rule in rules)


# --- Chart ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def summary_chart(wb):
    charts = wb["Summary"]._charts
    assert len(charts) == 1
    return charts[0]


def test_chart_has_one_series_per_country(summary_chart):
    assert len(summary_chart.series) == len(SAMPLE["country_order"])


def test_chart_data_labels_show_only_the_value(summary_chart):
    """Excel defaults an unwritten flag to ON, printing "Vietnam, Jan '26, 100%"."""
    for series in summary_chart.series:
        labels = series.dLbls
        assert labels.showVal is True
        assert not any((labels.showSerName, labels.showCatName, labels.showLegendKey,
                        labels.showPercent, labels.showBubbleSize))
        assert None not in (labels.showSerName, labels.showCatName, labels.showLegendKey,
                            labels.showPercent, labels.showBubbleSize)


def test_chart_categories_use_a_text_reference(summary_chart):
    """Month labels are text; a numeric ref makes Excel drop the axis labels."""
    for series in summary_chart.series:
        assert series.cat.strRef is not None
        assert series.cat.numRef is None


def test_chart_axes_are_visible(summary_chart):
    assert summary_chart.x_axis.delete is False
    assert summary_chart.y_axis.delete is False


def test_chart_series_have_distinct_solid_colours(summary_chart):
    colours = [s.graphicalProperties.solidFill for s in summary_chart.series]
    assert all(colours) and len(set(colours)) == len(colours)


# --- Content against the July 2026 reference ------------------------------------

needs_reference = pytest.mark.skipif(not reference_data.REFERENCE_PATH.exists(),
                                     reason="reference workbook not present (confidential, not in git)")


def _clean(value):
    if isinstance(value, float):
        return round(value, 10)
    if isinstance(value, str):
        return value.strip() or None
    return value


def table_rows(ws, name):
    return [[_clean(c.value) for c in row] for row in ws[ws.tables[name].ref]]


@pytest.fixture(scope="module")
def reference_wb():
    return reference_data.load_reference()


@pytest.fixture(scope="module")
def generated_wb(reference_wb):
    inputs = reference_data.all_inputs(reference_wb)
    return build(inputs, reference_data.MONTH_NAME, reference_data.YEAR)


@needs_reference
@pytest.mark.parametrize("sheet, table", [("Summary", "Table3"), ("Summary", "Table2"), ("Visibility", "Table9"),
                                          ("Top Performers", "Table8"), ("Follow-Up Required", "Table6")])
def test_table_content_matches_reference(reference_wb, generated_wb, sheet, table):
    expected = table_rows(reference_wb[sheet], table)
    if table == "Table2":
        expected[0][-1] = "Jul '26"  # the reference's last month header was mistyped "Jul '27" by hand
    assert table_rows(generated_wb[sheet], table) == expected


@needs_reference
def test_summary_sources_match_reference(reference_wb, generated_wb):
    ref, ws = reference_wb["Summary"], generated_wb["Summary"]
    assert (ws["B7"].value, ws["D7"].value) == (ref["A5"].value, ref["B5"].value)


@needs_reference
def test_yearly_content_matches_reference(reference_wb, generated_wb):
    """Same header and rows; the generated sheet sits one column to the right."""
    ref, ws = reference_wb["Yearly Performance"], generated_wb["Yearly Performance"]
    assert ws.max_row == ref.max_row
    for row in range(7, ref.max_row + 1):
        expected = [_clean(ref.cell(row=row, column=c).value) for c in range(1, ref.max_column + 1)]
        actual = [_clean(ws.cell(row=row, column=c + 1).value) for c in range(1, ref.max_column + 1)]
        if row > 7:  # the Total formulas point at each sheet's own month columns
            assert str(actual[-1]).startswith("=IFERROR(AVERAGE(") and str(expected[-1]).startswith("=IFERROR(AVERAGE(")
            expected, actual = expected[:-1], actual[:-1]
        assert actual == expected, f"row {row}"

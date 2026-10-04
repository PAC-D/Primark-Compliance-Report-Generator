"""The generated summary workbook must match the reference layout.

The reference is the pipeline's own July 2026 output after hand-polishing in
Excel. These tests drive the real sheet builders with the reference's own data
and compare structural fingerprints, so any drift in layout, number formats,
table definitions or chart configuration fails loudly.

A short list of hand-editing artifacts in the reference is normalised away
before comparing - see `_normalise_reference` for each one and why.
"""

import pytest
from openpyxl import Workbook

from . import reference_data
from .xlsx_fingerprint import diff_fingerprints, sheet_fingerprint

from tps.reports.summary_excel import (
    _build_follow_up_required_sheet,
    _build_summary_sheet,
    _build_top_performers_sheet,
    _build_visibility_sheet,
    _build_yearly_performance_sheet,
)

# The reference holds real supplier names and emails, so it stays out of git.
if not reference_data.REFERENCE_PATH.exists():
    pytest.skip("reference workbook not present (confidential, not in git)",
                allow_module_level=True)

SHEETS = ["Summary", "Visibility", "Top Performers", "Follow-Up Required",
          "Yearly Performance"]


@pytest.fixture(scope="module")
def reference_wb():
    return reference_data.load_reference()


@pytest.fixture(scope="module")
def inputs(reference_wb):
    return reference_data.all_inputs(reference_wb)


@pytest.fixture(scope="module")
def generated_wb(inputs):
    wb = Workbook()
    wb.remove(wb.active)

    _build_summary_sheet(
        wb, inputs["sources"], inputs["compliance_data"], inputs["country_data"],
        inputs["chart_labels"], inputs["country_order"],
        reference_data.MONTH_NAME, reference_data.YEAR,
    )
    _build_visibility_sheet(
        wb, inputs["line_details"], inputs["line_totals"],
        reference_data.MONTH_NAME, reference_data.YEAR,
    )
    _build_top_performers_sheet(
        wb, inputs["top_suppliers"], reference_data.MONTH_NAME, reference_data.YEAR,
    )
    _build_follow_up_required_sheet(
        wb, inputs["suppliers_below"], inputs["email_map"],
        f"{reference_data.MONTH_NAME} {reference_data.YEAR}",
    )
    _build_yearly_performance_sheet(
        wb, inputs["all_supplier_trend"], inputs["month_labels"], reference_data.YEAR,
    )
    return wb


def _normalise_reference(sheet, fp):
    """Reconcile the reference with what we deliberately render differently.

    Two categories: hand-editing artifacts in the reference that we don't
    reproduce, and agreed departures from it.
    """
    # Departure: the reference has sheet gridlines showing; we keep them hidden,
    # as the generator always did.
    fp["show_gridlines"] = False

    if sheet == "Summary":
        # Departure: the single title row is split into title + subtitle.
        fp["cells"]["A1"]["value"] = "TPS COMPLIANCE REPORT"
        fp["cells"]["A2"] = {
            "value": f"Summary for {reference_data.MONTH_NAME} "
                     f"{reference_data.YEAR}",
            "number_format": "General", "bold": False, "size": 11.0,
            "font": "595959", "fill": None, "halign": "center",
        }
        fp["merged"] = sorted(fp["merged"] + ["A2:F2"])

        # Widths left on empty columns while editing.
        for letter in ("O", "R", "T"):
            fp["column_widths"].pop(letter, None)
        # The trend header was filled on its first and last cell only, in
        # 1F4E78 - a shade off the 1F4E79 used everywhere else. We fill the
        # whole header row uniformly instead.
        for coord in ("D28", "E28", "F28", "G28", "H28", "I28", "J28", "K28"):
            fp["cells"][coord]["fill"] = "1F4E79"
            fp["cells"][coord]["bold"] = True
            fp["cells"][coord]["font"] = "FFFFFF"
            fp["cells"][coord]["halign"] = "center"
            fp["cells"][coord]["number_format"] = "General"
        # K28 read "Jul '27" for a July 2026 report.
        fp["cells"]["K28"]["value"] = "Jul '26"
        # A9:A16 were set to 10pt/left but the last country row was missed.
        fp["cells"]["A17"]["size"] = 10.0
        fp["cells"]["A17"]["halign"] = "left"
        # One month column got right-aligned on its own.
        for row in range(29, 38):
            fp["cells"][f"J{row}"]["halign"] = None
        # The trend table's column name follows its (corrected) header cell.
        fp["tables"]["Table2"]["columns"][-1]["name"] = "Jul '26"

    elif sheet == "Visibility":
        for letter in ("F", "G"):
            fp["column_widths"].pop(letter, None)

    elif sheet == "Top Performers":
        # Column B alone carries white/grey banding painted over the table's
        # own row stripes. We let the table style band all columns.
        for row in range(3, 75):
            fp["cells"][f"B{row}"]["fill"] = None

    elif sheet == "Follow-Up Required":
        fp["cells"]["C6"]["fill"] = None       # one stray white cell
        fp["row_heights"].pop(7, None)         # one row resized by hand
        # The final row missed the formatting applied to the rest of the column.
        fp["cells"]["A12"]["halign"] = "center"
        fp["cells"]["H12"]["size"] = 11.0
        # One email cell picked up Excel's hyperlink blue.
        fp["cells"]["H4"]["font"] = None

    elif sheet == "Yearly Performance":
        for letter in ("K", "L", "N", "O", "P"):
            fp["column_widths"].pop(letter, None)
        # Filter stopped at H154; the data runs to J155.
        fp["auto_filter"] = "A7:J155"

    return fp


def _compare(sheet, reference_wb, generated_wb, **kwargs):
    expected = _normalise_reference(
        sheet, sheet_fingerprint(reference_wb[sheet], **kwargs)
    )
    actual = sheet_fingerprint(generated_wb[sheet], **kwargs)
    diffs = diff_fingerprints(expected, actual)
    assert not diffs, f"{sheet} differs from reference:\n" + "\n".join(diffs[:60])


def test_sheet_order_matches_reference(reference_wb, generated_wb):
    assert generated_wb.sheetnames == reference_wb.sheetnames


@pytest.mark.parametrize("sheet", SHEETS)
def test_sheet_matches_reference(sheet, reference_wb, generated_wb):
    _compare(sheet, reference_wb, generated_wb)


def _one_supplier():
    """A row shaped like get_suppliers_below_threshold() returns - no month_label."""
    return {
        "sl": 1, "origin_country": "Turkey", "supplier": "ACME TEXTILES",
        "factory_count": 2, "dest_po_count": 33, "reflected_lines": 143,
        "avg_3month": 0.0,
    }


def test_follow_up_title_carries_report_month_without_month_label_rows():
    wb = Workbook()
    wb.remove(wb.active)

    _build_follow_up_required_sheet(wb, [_one_supplier()], {}, "July 2026")

    assert wb["Follow-Up Required"]["A1"].value == (
        "Follow-Up Required (Avg. Compliance <40% – Last 3 Months) – July 2026"
    )


# --- Chart rendering ---------------------------------------------------------

@pytest.fixture(scope="module")
def summary_chart(generated_wb):
    charts = generated_wb["Summary"]._charts
    assert len(charts) == 1
    return charts[0]


def test_chart_data_labels_show_only_the_value(summary_chart):
    """Excel defaults an unwritten flag to ON, printing "Vietnam, Jan '26, 100%"."""
    for series in summary_chart.series:
        labels = series.dLbls
        assert labels is not None
        assert labels.showVal is True
        assert labels.showSerName is False
        assert labels.showCatName is False
        assert labels.showLegendKey is False
        assert labels.showPercent is False
        assert labels.showBubbleSize is False


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
    assert all(colours), "every series needs an explicit fill"
    assert len(set(colours)) == len(colours), "series colours must be distinct"


# --- Sheet presentation ------------------------------------------------------

@pytest.mark.parametrize("sheet", SHEETS)
def test_sheet_hides_gridlines(sheet, generated_wb):
    assert generated_wb[sheet].sheet_view.showGridLines is False


def test_summary_title_and_subtitle_are_separate_rows(generated_wb):
    ws = generated_wb["Summary"]
    assert ws["A1"].value == "TPS COMPLIANCE REPORT"
    assert ws["A2"].value == "Summary for July 2026"

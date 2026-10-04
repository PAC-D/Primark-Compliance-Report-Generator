"""Monthly summary workbook: Summary, Visibility, Top Performers,
Follow-Up Required and Yearly Performance sheets.

Layout is pinned to a hand-polished reference workbook by
tests/test_summary_excel_layout.py - change widths/styles there first.
"""

import calendar
from datetime import date

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.axis import ChartLines
from openpyxl.chart.data_source import AxDataSource, NumFmt, StrRef
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.chart.text import RichText, Text
from openpyxl.chart.title import Title
from openpyxl.drawing.line import LineProperties
from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, TwoCellAnchor
from openpyxl.drawing.text import (
    CharacterProperties,
    Paragraph,
    ParagraphProperties,
    RegularTextRun,
    RichTextProperties,
)
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableColumn, TableStyleInfo

from tps.common import get_report_month
from tps.metrics.summary import (
    get_all_suppliers_trend,
    get_summary_country_compliance,
    get_summary_country_monthly_trend,
    get_summary_line_details,
    get_summary_sources,
    get_supplier_emails_map,
    get_suppliers_below_threshold,
    get_top_suppliers,
)

ACCENT = "1F4E79"
TOTAL_ROW_FILL = "D6E4F0"

SUBTITLE_COLOUR = "595959"
SECTION_FONT = Font(bold=True, size=11, color=ACCENT)
HEADER_FONT = Font(bold=True, size=11, color="FFFFFF")
SUBTITLE_FONT = Font(size=11, color=SUBTITLE_COLOUR)
ACCENT_FILL = PatternFill(start_color=ACCENT, end_color=ACCENT, fill_type="solid")

# Office accent palette, then darker variants - the cycle Excel itself uses once
# a chart runs past six series (see the reference chart's colours).
SERIES_COLOURS = ["4F81BD", "C0504D", "9BBB59", "8064A2", "4BACC6",
                  "F79646", "254061", "953735", "77933C"]
GRIDLINE_COLOUR = "D9D9D9"

CENTER = Alignment(horizontal="center")
CENTER_MIDDLE = Alignment(horizontal="center", vertical="center")
LEFT = Alignment(horizontal="left")
RIGHT = Alignment(horizontal="right")


def render_summary_excel(report_month: date | None = None) -> Workbook:
    if report_month is None:
        report_month = get_report_month()

    wb = Workbook()
    wb.remove(wb.active)

    sources = get_summary_sources(report_month)
    compliance_data = get_summary_country_compliance(report_month)
    country_data, chart_labels, country_order = get_summary_country_monthly_trend(report_month)
    line_details, line_totals = get_summary_line_details(report_month)
    top_suppliers = get_top_suppliers(report_month)
    suppliers_below = get_suppliers_below_threshold(report_month)
    all_supplier_trend, month_labels = get_all_suppliers_trend(report_month)
    email_map = get_supplier_emails_map()

    month_name = report_month.strftime("%B")
    year = report_month.year

    _build_summary_sheet(wb, sources, compliance_data, country_data,
                         chart_labels, country_order, month_name, year)
    _build_visibility_sheet(wb, line_details, line_totals, month_name, year)
    _build_top_performers_sheet(wb, top_suppliers, month_name, year)
    _build_follow_up_required_sheet(wb, suppliers_below, email_map, f"{month_name} {year}")
    _build_yearly_performance_sheet(wb, all_supplier_trend, month_labels, year)

    return wb


def _set_widths(ws, widths):
    for letter, width in widths.items():
        ws.column_dimensions[letter].width = width


def _add_table(ws, name, ref, style, columns, totals_row_count=None):
    table = Table(displayName=name, ref=ref, totalsRowCount=totals_row_count,
                  tableColumns=columns)
    table.tableStyleInfo = TableStyleInfo(
        name=style, showRowStripes=True, showColumnStripes=False,
        showFirstColumn=False, showLastColumn=False,
    )
    ws.add_table(table)
    return table


def _title(ws, ref, text, size=13):
    ws.merge_cells(ref)
    cell = ws[ref.split(":")[0]]
    cell.value = text
    cell.font = Font(bold=True, size=size, color=ACCENT)
    cell.alignment = CENTER_MIDDLE
    return cell


def _chart_text(text, size, bold=True, colour=ACCENT, rotation=None):
    """A styled chart/axis title. openpyxl's plain string titles are unstyled."""
    props = CharacterProperties(sz=size * 100, b=bold, solidFill=colour)
    paragraph = Paragraph(
        pPr=ParagraphProperties(defRPr=props),
        r=[RegularTextRun(rPr=props, t=text)],
    )
    body = RichTextProperties(rot=rotation, vert="horz")
    return Title(tx=Text(rich=RichText(bodyPr=body, p=[paragraph])))


def _value_only_labels():
    """Every flag must be explicit - Excel treats an omitted flag as ON, which
    is what turned the labels into "Vietnam, Jan '26, 100.0%"."""
    return DataLabelList(
        dLblPos="outEnd",
        showVal=True,
        showSerName=False,
        showCatName=False,
        showLegendKey=False,
        showPercent=False,
        showBubbleSize=False,
    )


def _add_trend_chart(ws, header_row, first_row, last_row, label_col, last_value_col):
    """Clustered column chart: one series per country, months as categories."""
    chart = BarChart()
    chart.type = "col"
    chart.grouping = "clustered"
    chart.gapWidth = 100
    chart.overlap = -24
    chart.title = _chart_text("Compliance Rate by Country (%)", 16)

    data = Reference(ws, min_col=label_col, min_row=first_row,
                     max_col=last_value_col, max_row=last_row)
    chart.add_data(data, from_rows=True, titles_from_data=True)

    # Month labels are text, so they need a string reference; openpyxl's
    # set_categories() writes a numeric one, which Excel renders as no labels.
    cats = Reference(ws, min_col=label_col + 1, min_row=header_row,
                     max_col=last_value_col, max_row=header_row)
    category_ref = AxDataSource(strRef=StrRef(f=str(cats)))

    for index, series in enumerate(chart.series):
        series.cat = category_ref
        series.dLbls = _value_only_labels()
        colour = SERIES_COLOURS[index % len(SERIES_COLOURS)]
        series.graphicalProperties = GraphicalProperties(solidFill=colour)
        series.graphicalProperties.line.noFill = True

    chart.x_axis.title = _chart_text("Month", 9)
    chart.y_axis.title = _chart_text("Compliance rate", 9, rotation=-5400000)
    chart.y_axis.numFmt = NumFmt(formatCode="0.0%", sourceLinked=True)

    # Without an explicit delete=False Excel drops the axis and its labels.
    for axis in (chart.x_axis, chart.y_axis):
        axis.delete = False
        axis.tickLblPos = "nextTo"
        axis.txPr = RichText(
            p=[Paragraph(pPr=ParagraphProperties(
                defRPr=CharacterProperties(sz=900, solidFill="595959")))]
        )

    chart.x_axis.majorGridlines = None
    chart.y_axis.majorGridlines = ChartLines(
        spPr=GraphicalProperties(
            ln=LineProperties(w=9525, solidFill=GRIDLINE_COLOUR))
    )

    chart.legend.position = "b"
    chart.legend.overlay = False

    chart.anchor = TwoCellAnchor(
        _from=AnchorMarker(col=0, colOff=0, row=22, rowOff=359),
        to=AnchorMarker(col=33, colOff=586684, row=65, rowOff=106829),
    )
    ws.add_chart(chart)


def _build_country_trend_block(ws, country_data, chart_labels, country_order,
                               header_row=28, label_col=4):
    """Countries down the rows, months across the columns, as an Excel table."""
    last_value_col = label_col + len(chart_labels)

    header = ws.cell(row=header_row, column=label_col, value="Country")
    headers = [header]
    for offset, label in enumerate(chart_labels, 1):
        headers.append(ws.cell(row=header_row, column=label_col + offset, value=label))
    for cell in headers:
        cell.font = HEADER_FONT
        cell.fill = ACCENT_FILL
        cell.alignment = CENTER

    for i, country in enumerate(country_order):
        row = header_row + 1 + i
        name_cell = ws.cell(row=row, column=label_col, value=country)
        name_cell.font = Font(bold=True, size=11)

        rates = country_data.get(country, [])
        for j in range(len(chart_labels)):
            rate = rates[j] if j < len(rates) else None
            # No shipments that month: leave the cell blank so the chart shows a gap, not 0%.
            cell = ws.cell(row=row, column=label_col + 1 + j,
                           value=None if rate is None else rate / 100.0)
            cell.number_format = "0.0%"

    first_row = header_row + 1
    last_row = header_row + len(country_order)

    columns = [TableColumn(id=1, name="Country")]
    for i, label in enumerate(chart_labels, 2):
        columns.append(TableColumn(id=i, name=label))

    ref = (f"{get_column_letter(label_col)}{header_row}"
           f":{get_column_letter(last_value_col)}{last_row}")
    _add_table(ws, "Table2", ref, "TableStyleLight9", columns)

    _add_trend_chart(ws, header_row, first_row, last_row, label_col, last_value_col)


def _build_summary_sheet(wb, sources, compliance_data, country_data,
                         chart_labels, country_order, month_name, year):
    ws = wb.create_sheet("Summary")
    ws.sheet_view.showGridLines = False

    _title(ws, "A1:F1", "TPS COMPLIANCE REPORT", size=14)
    ws.row_dimensions[1].height = 25

    ws.merge_cells("A2:F2")
    ws["A2"] = f"Summary for {month_name} {year}"
    ws["A2"].font = SUBTITLE_FONT
    ws["A2"].alignment = CENTER_MIDDLE

    ws["A3"] = "Sources"
    ws["A3"].font = SECTION_FONT

    for col, label in ((1, "Supplier"), (2, "Factory")):
        cell = ws.cell(row=4, column=col, value=label)
        cell.font = HEADER_FONT
        cell.fill = ACCENT_FILL
        cell.alignment = CENTER

    for col, value in ((1, sources["total_suppliers"]), (2, sources["total_factories"])):
        cell = ws.cell(row=5, column=col, value=value)
        cell.font = Font(size=10)
        cell.alignment = CENTER

    ws["A7"] = "Volume (Compliant Only)"
    ws["A7"].font = SECTION_FONT

    # A8:B18 - Table3 supplies the header styling and the Average totals row.
    for col, label in ((1, "Country"), (2, "Compliance Score")):
        cell = ws.cell(row=8, column=col, value=label)
        cell.font = Font(bold=True, size=11)
        cell.alignment = CENTER

    for i, item in enumerate(compliance_data):
        row = 9 + i
        name_cell = ws.cell(row=row, column=1, value=item["country"])
        name_cell.font = Font(size=10)
        name_cell.alignment = LEFT

        rate_cell = ws.cell(row=row, column=2, value=item["compliance_rate"] / 100.0)
        rate_cell.number_format = "0%"

    totals_row = 9 + len(compliance_data)
    label_cell = ws.cell(row=totals_row, column=1, value="Average")
    label_cell.font = Font(size=10)
    label_cell.alignment = LEFT

    average_cell = ws.cell(row=totals_row, column=2,
                           value="=SUBTOTAL(101,Table3[Compliance Score])")
    average_cell.number_format = "0%"
    average_cell.font = Font(size=10)
    average_cell.alignment = RIGHT

    _add_table(
        ws, "Table3", f"A8:B{totals_row}", "TableStyleMedium9",
        [
            TableColumn(id=1, name="Country", totalsRowLabel="Average"),
            TableColumn(id=2, name="Compliance Score", totalsRowFunction="average"),
        ],
        totals_row_count=1,
    )

    _build_country_trend_block(ws, country_data, chart_labels, country_order)

    _set_widths(ws, {"A": 22.0, "B": 24.36, "C": 15.0, "D": 11.18,
                     "E": 7.18, "F": 7.0, "G": 7.36, "H": 6.82})
    ws.freeze_panes = "A2"


def _build_visibility_sheet(wb, line_details, line_totals, month_name, year):
    ws = wb.create_sheet("Visibility")
    ws.sheet_view.showGridLines = False

    _title(ws, "A1:E1", f"Visibility – {month_name} {year}")
    ws.row_dimensions[1].height = 16.5

    headers = ["Origin Country", "Destination PO", "Reflected Lines",
               "Approved", "Rejected"]
    for col, label in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col, value=label)
        cell.font = HEADER_FONT
        cell.fill = ACCENT_FILL
        cell.alignment = CENTER

    fields = ["country", "dest_po_count", "reflected_lines", "approved", "rejected"]
    for i, item in enumerate(line_details):
        row = 3 + i
        for col, field in enumerate(fields, 1):
            ws.cell(row=row, column=col, value=item[field])

    totals_row = 3 + len(line_details)
    total_fill = PatternFill(start_color=TOTAL_ROW_FILL, end_color=TOTAL_ROW_FILL,
                             fill_type="solid")

    label_cell = ws.cell(row=totals_row, column=1, value="Total")
    label_cell.font = Font(size=10)
    label_cell.alignment = LEFT
    label_cell.fill = total_fill

    for col, header in enumerate(headers[1:], 2):
        cell = ws.cell(row=totals_row, column=col,
                       value=f"=SUBTOTAL(109,Table9[{header}])")
        cell.font = Font(size=10)
        cell.alignment = RIGHT
        cell.fill = total_fill

    columns = [TableColumn(id=1, name="Origin Country", totalsRowLabel="Total")]
    for i, header in enumerate(headers[1:], 2):
        columns.append(TableColumn(id=i, name=header, totalsRowFunction="sum"))

    _add_table(ws, "Table9", f"A2:E{totals_row}", "TableStyleMedium2", columns,
               totals_row_count=1)

    _set_widths(ws, {"A": 24.45, "B": 16.63, "C": 33.45, "D": 18.36, "E": 15.82})
    ws.freeze_panes = "A3"


def _build_top_performers_sheet(wb, top_suppliers, month_name, year):
    ws = wb.create_sheet("Top Performers")
    ws.sheet_view.showGridLines = False

    _title(ws, "A1:G1", f"Top Suppliers  – {month_name} {year}")
    ws.row_dimensions[1].height = 16.5

    headers = ["#", "Origin", "Supplier", "No. of Factories", "Destination PO",
               "Reflected Lines", "Compliance Score"]
    for col, label in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col, value=label)
        cell.font = HEADER_FONT
        cell.alignment = CENTER

    fields = ["origin_countries", "supplier", "factory_count", "dest_po_count",
              "reflected_lines"]
    for i, supplier in enumerate(top_suppliers):
        row = 3 + i

        index_cell = ws.cell(row=row, column=1, value=supplier["sl"])
        index_cell.font = Font(size=10)
        index_cell.alignment = CENTER

        for col, field in enumerate(fields, 2):
            ws.cell(row=row, column=col, value=supplier[field])

        rate_cell = ws.cell(row=row, column=7,
                            value=supplier["compliance_rate"] / 100.0)
        rate_cell.number_format = "0%"

    last_row = 2 + len(top_suppliers)
    columns = [TableColumn(id=i, name=label) for i, label in enumerate(headers, 1)]
    _add_table(ws, "Table8", f"A2:G{last_row}", "TableStyleLight9", columns)

    _set_widths(ws, {"A": 5.0, "B": 27.82, "C": 69.18, "D": 17.45,
                     "E": 16.63, "F": 17.18, "G": 19.63})
    ws.freeze_panes = "A3"

# --- Follow-Up Required sheet ---------------------------------------------------

FOLLOW_UP_HEADER_FILL = PatternFill(start_color="156082", end_color="156082", fill_type="solid")
FOLLOW_UP_HEADER_FONT = Font(bold=True, size=10, color="FFFFFF")
FOLLOW_UP_HEADERS = ["Sl ", "Origin Country ", "Supplier Name ", "No of Factories ",
                     "Destination PO Qty ", "Reflected Lines ", "Compliance Score ", "Email "]
# Header cells that are explicitly centred; the rest keep the default alignment.
FOLLOW_UP_CENTERED = {2, 4, 5, 6, 7}
FOLLOW_UP_WIDTHS = {"A": 5.0, "B": 22.0, "C": 45.0, "D": 17.45,
                    "E": 16.63, "F": 17.18, "G": 19.63, "H": 92.82}


def _build_follow_up_required_sheet(wb, suppliers_below, email_map, month_label):
    ws = wb.create_sheet("Follow-Up Required")
    ws.sheet_view.showGridLines = False

    _title(ws, "A1:H1", f"Follow-Up Required (Avg. Compliance <40% – Last 3 Months) – {month_label}")
    ws.row_dimensions[1].height = 17.0

    for col, label in enumerate(FOLLOW_UP_HEADERS, 1):
        cell = ws.cell(row=2, column=col, value=label)
        cell.font = FOLLOW_UP_HEADER_FONT
        cell.fill = FOLLOW_UP_HEADER_FILL
        if col in FOLLOW_UP_CENTERED:
            cell.alignment = CENTER

    for i, supplier in enumerate(suppliers_below):
        row = 3 + i

        index_cell = ws.cell(row=row, column=1, value=supplier["sl"])
        index_cell.font = Font(size=10)
        index_cell.alignment = CENTER

        ws.cell(row=row, column=2, value=supplier["origin_country"])
        ws.cell(row=row, column=3, value=supplier["supplier"])

        for col, field in ((4, "factory_count"), (5, "dest_po_count"),
                           (6, "reflected_lines")):
            cell = ws.cell(row=row, column=col, value=supplier[field])
            cell.alignment = CENTER

        rate = supplier.get("avg_3month")
        if rate is None:
            rate = supplier.get("compliance_rate", 0)
        rate_cell = ws.cell(row=row, column=7, value=rate / 100.0)
        rate_cell.number_format = "0%"
        rate_cell.alignment = CENTER

        ws.cell(row=row, column=8,
                value=email_map.get(supplier["supplier"].strip().lower(), ""))

    last_row = 2 + len(suppliers_below)
    columns = [TableColumn(id=i, name=label) for i, label in enumerate(FOLLOW_UP_HEADERS, 1)]
    _add_table(ws, "Table6", f"A2:H{last_row}", "TableStyleLight9", columns)

    _set_widths(ws, FOLLOW_UP_WIDTHS)
    ws.freeze_panes = "A3"


# --- Yearly Performance sheet ---------------------------------------------------

THIN_BORDER = Border(left=Side(style="thin"), right=Side(style="thin"),
                     top=Side(style="thin"), bottom=Side(style="thin"))
BAND_FILL = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
YEAR_FILL = PatternFill(start_color="4A5568", end_color="4A5568", fill_type="solid")
YEARLY_HEADER_FILL = PatternFill(start_color="1B2838", end_color="1B2838", fill_type="solid")

# Widths carried over from the reference workbook; extra months fall back to
# the width used by most month columns.
MONTH_WIDTHS = [10.45, 10.63, 11.0, 10.45, 11.36, 10.45, 13.63]
DEFAULT_MONTH_WIDTH = 10.45

YEAR_BAND_ROW = 6
HEADER_ROW = 7
FIRST_DATA_ROW = 8


def _build_yearly_performance_sheet(wb, supplier_trend, month_labels, year):
    ws = wb.create_sheet("Yearly Performance")
    ws.sheet_view.showGridLines = False

    num_months = len(month_labels)
    last_month_col = 2 + num_months
    total_col = last_month_col + 1
    last_month_letter = get_column_letter(last_month_col)

    _title(ws, f"A1:{last_month_letter}1",
           f"Suppliers Yearly Performance – January {year} "
           f"to {chart_end_caption(month_labels, year)}")
    ws.row_dimensions[1].height = 16.5

    ws.merge_cells(f"A{YEAR_BAND_ROW}:B{YEAR_BAND_ROW}")
    ws.merge_cells(f"C{YEAR_BAND_ROW}:{last_month_letter}{YEAR_BAND_ROW}")
    year_cell = ws.cell(row=YEAR_BAND_ROW, column=3, value=year)
    year_cell.font = Font(bold=True, color="FFFFFF", size=11)
    year_cell.fill = YEAR_FILL
    year_cell.alignment = CENTER_MIDDLE
    year_cell.border = Border(bottom=Side(style="thin"))

    headers = ["#", "Supplier Name"] + list(month_labels) + ["Total"]
    for col, label in enumerate(headers, 1):
        cell = ws.cell(row=HEADER_ROW, column=col, value=label)
        cell.font = Font(bold=True, color="FFFFFF", size=9)
        cell.fill = YEARLY_HEADER_FILL
        cell.alignment = CENTER_MIDDLE
        cell.border = THIN_BORDER

    ws.column_dimensions["A"].width = 6.45
    ws.column_dimensions["B"].width = 81.36
    for i in range(num_months):
        width = MONTH_WIDTHS[i] if i < len(MONTH_WIDTHS) else DEFAULT_MONTH_WIDTH
        ws.column_dimensions[get_column_letter(3 + i)].width = width
    ws.column_dimensions[get_column_letter(total_col)].width = 7.82

    for idx, supplier in enumerate(supplier_trend, start=1):
        row = HEADER_ROW + idx
        banded = idx % 2 == 0

        ws.cell(row=row, column=1, value=idx).alignment = CENTER
        ws.cell(row=row, column=2, value=supplier["supplier"]).alignment = LEFT

        for i, rate in enumerate(supplier["rates"]):
            cell = ws.cell(row=row, column=3 + i)
            # A month with no data stays genuinely empty, so AVERAGE skips it.
            if rate is not None:
                cell.value = rate / 100.0
                cell.number_format = "0.00%"
                if rate < 40:
                    cell.font = Font(color="DC2626", bold=True, size=11)
                elif rate < 60:
                    cell.font = Font(color="EA580C", size=11)
            cell.alignment = CENTER

        total_cell = ws.cell(row=row, column=total_col)
        total_cell.value = f'=IFERROR(AVERAGE(C{row}:{last_month_letter}{row}),"")'
        total_cell.number_format = "0.00%"
        total_cell.alignment = CENTER
        total_cell.font = Font(bold=True, size=11)

        for col in range(1, total_col + 1):
            cell = ws.cell(row=row, column=col)
            cell.border = THIN_BORDER
            if banded:
                cell.fill = BAND_FILL

    last_row = HEADER_ROW + len(supplier_trend)
    ws.auto_filter.ref = f"A{HEADER_ROW}:{get_column_letter(total_col)}{last_row}"
    ws.freeze_panes = f"A{FIRST_DATA_ROW}"


def chart_end_caption(month_labels, year):
    """"July 2026" from the last chart label ("Jul '26"); just the year if unparseable."""
    try:
        m_abbr, yy = month_labels[-1].split(" '")
        return f"{calendar.month_name[list(calendar.month_abbr).index(m_abbr)]} 20{int(yy)}"
    except (IndexError, ValueError):
        return f"{year}"

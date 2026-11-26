"""Monthly summary workbook: Summary, Visibility, Top Performers,
Follow-Up Required and Yearly Performance sheets.

Every sheet shares one frame (margin column, title, subtitle, accent rule, print
setup) and every table one custom table style, so the workbook reads as one
report. tests/test_summary_excel.py checks the content still matches the
hand-checked July 2026 reference.
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
from openpyxl.formatting.rule import ColorScaleRule, DataBarRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.styles.differential import DifferentialStyle
from openpyxl.styles.table import TableStyle, TableStyleElement, TableStyleList
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableColumn, TableStyleInfo

from tps.common import get_report_month
from tps.metrics.kpi import region_working_days
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

# The PDF reports' palette.
NAVY = "002A62"
CYAN = "00A2D3"
TINT = "E8F6FB"
STRIPE = "F5F9FC"
MUTED = "5B7486"
INK = "1F2937"
LINE = "DCE4EC"
ALERT = "DC2626"
LOW_TEXT, LOW_FILL = "B91C1C", "FDE2E1"
MID_TEXT, MID_FILL = "B45309", "FEF3C7"
LINK = "1C5CAB"

# Chart series, checked for colour-blind separation; a tenth country reuses the first colour.
SERIES_COLOURS = ["1C5CAB", "EB6834", "1BAF7A", "EDA100", "E87BA4",
                  "008300", "4A3AA7", "E34948", "00A2D3"]

TABLE_STYLE = "TPS Table"
HEADER_FONT = Font(bold=True, size=10, color="FFFFFF")
BODY_FONT = Font(size=10, color=INK)
TOTAL_FONT = Font(bold=True, size=10, color=NAVY)
CENTER = Alignment(horizontal="center", vertical="center")
LEFT = Alignment(horizontal="left", vertical="center", indent=1)
RIGHT = Alignment(horizontal="right", vertical="center", indent=1)

FIRST_CONTENT_ROW = 6  # below the title, subtitle and accent rule


def summary_context(report_month: date) -> dict:
    """Everything the summary workbook (and the dashboard) shows for one month."""
    country_data, chart_labels, country_order = get_summary_country_monthly_trend(report_month)
    line_details, line_totals = get_summary_line_details(report_month)
    all_supplier_trend, month_labels = get_all_suppliers_trend(report_month)
    return {
        "sources": get_summary_sources(report_month),
        "compliance_data": get_summary_country_compliance(report_month),
        "country_data": country_data,
        "chart_labels": chart_labels,
        "country_order": country_order,
        "line_details": line_details,
        "line_totals": line_totals,
        "top_suppliers": get_top_suppliers(report_month),
        "suppliers_below": get_suppliers_below_threshold(report_month),
        "all_supplier_trend": all_supplier_trend,
        "month_labels": month_labels,
        "email_map": get_supplier_emails_map(),
        "working_days": region_working_days(report_month)["cn"],
        "days_in_month": calendar.monthrange(report_month.year, report_month.month)[1],
        "month_name": report_month.strftime("%B"),
        "year": report_month.year,
    }


def render_summary_excel(report_month: date | None = None) -> Workbook:
    if report_month is None:
        report_month = get_report_month()

    wb = Workbook()
    wb.remove(wb.active)

    c = summary_context(report_month)
    month_name, year = c["month_name"], c["year"]

    _build_summary_sheet(wb, c["sources"], c["compliance_data"], c["country_data"],
                         c["chart_labels"], c["country_order"], month_name, year,
                         (c["working_days"], c["days_in_month"]))
    _build_visibility_sheet(wb, c["line_details"], c["line_totals"], month_name, year)
    _build_top_performers_sheet(wb, c["top_suppliers"], month_name, year)
    _build_follow_up_required_sheet(wb, c["suppliers_below"], c["email_map"], f"{month_name} {year}")
    _build_yearly_performance_sheet(wb, c["all_supplier_trend"], c["month_labels"], year)

    wb.properties.title = f"TPS Compliance Report – {month_name} {year}"
    wb.properties.creator = "PAC-D"
    return wb


def _fill(colour):
    return PatternFill(fill_type="solid", start_color=colour, end_color=colour)


def _ensure_table_style(wb):
    """Register the custom table style once per workbook (openpyxl has no public API for it)."""
    if wb._table_styles is not None and any(s.name == TABLE_STYLE for s in wb._table_styles.tableStyle):
        return

    def dxf(**style):
        wb._differential_styles.append(DifferentialStyle(**style))
        return len(wb._differential_styles.styles) - 1

    hairline = Side(style="thin", color=LINE)
    elements = [
        TableStyleElement(type="wholeTable", dxfId=dxf(border=Border(bottom=hairline, horizontal=hairline))),
        TableStyleElement(type="headerRow", dxfId=dxf(fill=PatternFill(fill_type="solid", bgColor=NAVY),
                                                      font=Font(bold=True, color="FFFFFF"))),
        TableStyleElement(type="firstRowStripe", dxfId=dxf(fill=PatternFill(fill_type="solid", bgColor=STRIPE))),
        TableStyleElement(type="totalRow", dxfId=dxf(fill=PatternFill(fill_type="solid", bgColor=TINT),
                                                     font=Font(bold=True, color=NAVY),
                                                     border=Border(top=Side(style="medium", color=NAVY)))),
    ]
    wb._table_styles = TableStyleList(tableStyle=[
        TableStyle(name=TABLE_STYLE, pivot=False, table=True, tableStyleElement=elements)])


def _frame(ws, title, subtitle, last_col, tab_colour, accent=CYAN, print_title_rows=None):
    """Margin column, title, subtitle and accent rule (rows 1-5), and print setup."""
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = tab_colour
    ws.column_dimensions["A"].width = 2.5
    ws.row_dimensions[1].height = 10

    ws["B2"] = title
    ws["B2"].font = Font(bold=True, size=18, color=NAVY)
    ws.row_dimensions[2].height = 30
    ws["B3"] = subtitle
    ws["B3"].font = Font(size=10, color=MUTED)
    ws.row_dimensions[4].height = 6
    for col in range(2, last_col + 1):
        ws.cell(row=4, column=col).border = Border(bottom=Side(style="medium", color=accent))
    ws.row_dimensions[5].height = 10

    setup = ws.page_setup
    setup.orientation = "landscape"
    setup.paperSize = ws.PAPERSIZE_A4
    setup.fitToWidth, setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.page_margins.top, ws.page_margins.bottom = 0.5, 0.6
    ws.oddFooter.left.text, ws.oddFooter.left.size = f"{title} · {subtitle}", 8
    ws.oddFooter.right.text, ws.oddFooter.right.size = "Page &P of &N", 8
    if print_title_rows:
        ws.print_title_rows = print_title_rows


def _add_table(ws, name, first_row, first_col, headers, rows, aligns, formats,
               totals=None, widths=None):
    """An Excel table with its header at (first_row, first_col).

    totals maps a header to ("label", text) or (function, subtotal_code), e.g.
    ("average", 101), and adds a totals row. Returns the table's last row.
    """
    _ensure_table_style(ws.parent)
    for j, header in enumerate(headers):
        cell = ws.cell(row=first_row, column=first_col + j, value=header)
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal=aligns[j].horizontal, vertical="center",
                                   indent=aligns[j].indent, wrap_text=True)
    ws.row_dimensions[first_row].height = 24

    for i, values in enumerate(rows, 1):
        for j, value in enumerate(values):
            cell = ws.cell(row=first_row + i, column=first_col + j, value=value)
            cell.font, cell.alignment, cell.number_format = BODY_FONT, aligns[j], formats[j]
        ws.row_dimensions[first_row + i].height = 18

    last_row = first_row + len(rows)
    columns = [TableColumn(id=j + 1, name=header) for j, header in enumerate(headers)]
    if totals:
        last_row += 1
        ws.row_dimensions[last_row].height = 20
        for j, header in enumerate(headers):
            cell = ws.cell(row=last_row, column=first_col + j)
            cell.font, cell.alignment, cell.number_format = TOTAL_FONT, aligns[j], formats[j]
            if header not in totals:
                continue
            kind, value = totals[header]
            if kind == "label":
                cell.value = columns[j].totalsRowLabel = value
            else:
                cell.value = f"=SUBTOTAL({value},{name}[{header}])"
                columns[j].totalsRowFunction = kind

    ref = (f"{get_column_letter(first_col)}{first_row}"
           f":{get_column_letter(first_col + len(headers) - 1)}{last_row}")
    table = Table(displayName=name, ref=ref, totalsRowCount=1 if totals else None,
                  tableColumns=columns)
    table.tableStyleInfo = TableStyleInfo(name=TABLE_STYLE, showRowStripes=True,
                                          showColumnStripes=False, showFirstColumn=False,
                                          showLastColumn=False)
    ws.add_table(table)
    for j, width in enumerate(widths or []):
        ws.column_dimensions[get_column_letter(first_col + j)].width = width
    return last_row


def _data_bars(ws, ref, max_value=None):
    if max_value is None:
        rule = DataBarRule(start_type="min", end_type="max", color=CYAN, showValue=True)
    else:
        rule = DataBarRule(start_type="num", start_value=0, end_type="num", end_value=max_value,
                           color=CYAN, showValue=True)
    ws.conditional_formatting.add(ref, rule)


def _section(ws, row, col, text):
    ws.cell(row=row, column=col, value=text).font = Font(bold=True, size=12, color=NAVY)
    ws.row_dimensions[row].height = 22


def _chart_text(text, size, colour=NAVY, rotation=None):
    """A styled chart/axis title. openpyxl's plain string titles are unstyled."""
    props = CharacterProperties(sz=size * 100, b=True, solidFill=colour)
    paragraph = Paragraph(pPr=ParagraphProperties(defRPr=props), r=[RegularTextRun(rPr=props, t=text)])
    body = RichTextProperties(rot=rotation, vert="horz")
    return Title(tx=Text(rich=RichText(bodyPr=body, p=[paragraph])), overlay=False)


def _text_properties(size, colour):
    return RichText(p=[Paragraph(pPr=ParagraphProperties(
        defRPr=CharacterProperties(sz=size * 100, solidFill=colour)))])


def _value_only_labels():
    """Every flag must be explicit - Excel treats an omitted flag as ON, which
    is what turned the labels into "Vietnam, Jan '26, 100.0%"."""
    labels = DataLabelList(dLblPos="outEnd", showVal=True, showSerName=False, showCatName=False,
                           showLegendKey=False, showPercent=False, showBubbleSize=False)
    labels.txPr = _text_properties(7, MUTED)
    return labels


# --- Summary sheet ----------------------------------------------------------------

def _tile_cell(ws, row, first, last, value, font, number_format="General"):
    if last > first:
        ws.merge_cells(start_row=row, start_column=first, end_row=row, end_column=last)
    cell = ws.cell(row=row, column=first, value=value)
    cell.font, cell.number_format = font, number_format
    cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)


def _kpi_tile(ws, row, first, last, label, value, number_format, caption):
    """Label, big value and caption over three rows of columns first..last, under a cyan
    accent line. Tiles sit side by side; a white edge on the left keeps them apart."""
    _tile_cell(ws, row, first, last, label.upper(), Font(bold=True, size=8, color=MUTED))
    _tile_cell(ws, row + 1, first, last, value, Font(bold=True, size=24, color=NAVY), number_format)
    _tile_cell(ws, row + 2, first, last, caption, Font(size=8, color=MUTED))
    gap = Side(style="thick", color="FFFFFF")
    for r in range(row, row + 3):
        for col in range(first, last + 1):
            ws.cell(row=r, column=col).fill = _fill(STRIPE)
            ws.cell(row=r, column=col).border = Border(
                top=Side(style="thick", color=CYAN) if r == row else None,
                left=gap if col == first else None)


def _add_trend_chart(ws, header_row, last_row, label_col, last_value_col, top_row, last_col):
    """Clustered column chart: one series per country, months as categories."""
    chart = BarChart()
    chart.type = "col"
    chart.grouping = "clustered"
    chart.gapWidth = 80
    chart.overlap = -10
    chart.title = _chart_text("Compliance Rate by Country (%)", 13)

    data = Reference(ws, min_col=label_col, min_row=header_row + 1,
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
        series.graphicalProperties = GraphicalProperties(solidFill=SERIES_COLOURS[index % len(SERIES_COLOURS)])
        series.graphicalProperties.line.noFill = True

    chart.x_axis.title = _chart_text("Month", 9, colour=MUTED)
    chart.y_axis.title = _chart_text("Compliance rate", 9, colour=MUTED, rotation=-5400000)
    chart.y_axis.numFmt = NumFmt(formatCode="0%", sourceLinked=False)

    # Without an explicit delete=False Excel drops the axis and its labels.
    for axis in (chart.x_axis, chart.y_axis):
        axis.delete = False
        axis.tickLblPos = "nextTo"
        axis.txPr = _text_properties(9, MUTED)

    chart.x_axis.majorGridlines = None
    chart.y_axis.majorGridlines = ChartLines(
        spPr=GraphicalProperties(ln=LineProperties(w=6350, solidFill="E3E9EF")))
    chart.legend.position = "b"
    chart.legend.overlay = False
    chart.graphical_properties = GraphicalProperties(ln=LineProperties(noFill=True))

    # AnchorMarker rows/columns are zero-based: the chart starts on the row below top_row
    # and runs through last_col.
    chart.anchor = TwoCellAnchor(_from=AnchorMarker(col=1, row=top_row),
                                 to=AnchorMarker(col=last_col, row=top_row + 24))
    ws.add_chart(chart)


def _build_summary_sheet(wb, sources, compliance_data, country_data,
                         chart_labels, country_order, month_name, year, working_days=None):
    """working_days: (working days Monday to Friday, days in the month), shown as a tile when given."""
    ws = wb.create_sheet("Summary")
    months = len(chart_labels)
    last_col = max(5 + months, 15)  # trend table ends at column 5 + months; tiles reach O
    _frame(ws, "TPS Compliance Report", f"Summary for {month_name} {year}", last_col, NAVY)
    # The tiles share these columns with the tables below; the widths make the four tiles
    # B:C, D:G, H:K and L:O come out the same width (34, 36, 34, 34).
    for letter, width in (("B", 18), ("C", 16), ("D", 3), ("E", 16)):
        ws.column_dimensions[letter].width = width
    for col in range(6, 6 + max(months, 10)):
        ws.column_dimensions[get_column_letter(col)].width = 8.5

    tile_row = FIRST_CONTENT_ROW
    table_row = tile_row + 5  # tiles, a gap, the section labels, then the table headers
    average_row = table_row + len(compliance_data) + 1
    for r, height in ((tile_row, 18), (tile_row + 1, 36), (tile_row + 2, 16)):
        ws.row_dimensions[r].height = height
    _kpi_tile(ws, tile_row, 2, 3, "Suppliers", sources["total_suppliers"], "#,##0", "Sources this month")
    _kpi_tile(ws, tile_row, 4, 7, "Factories", sources["total_factories"], "#,##0", "Sources this month")
    _kpi_tile(ws, tile_row, 8, 11, "Average compliance", f"=C{average_row}", "0%", "Across countries")
    if working_days is not None:
        days, days_in_month = working_days
        _kpi_tile(ws, tile_row, 12, 15, "Working days", days, f'0" / {days_in_month}"', "Monday to Friday")

    _section(ws, table_row - 1, 5, "Compliance Rate by Country")
    last_scores = _add_table(
        ws, "Table3", table_row, 2, ["Country", "Compliance Score"],
        [(item["country"], item["compliance_rate"] / 100.0) for item in compliance_data],
        [LEFT, RIGHT], ["General", "0%"],
        totals={"Country": ("label", "Average"), "Compliance Score": ("average", 101)},
    )
    _data_bars(ws, f"C{table_row + 1}:C{last_scores - 1}", max_value=1)

    trend_rows = []
    for country in country_order:
        rates = country_data.get(country, [])
        # No shipments that month: leave the cell blank so the chart shows a gap, not 0%.
        trend_rows.append([country] + [None if j >= len(rates) or rates[j] is None else rates[j] / 100.0
                                       for j in range(months)])
    last_trend = _add_table(ws, "Table2", table_row, 5, ["Country"] + list(chart_labels), trend_rows,
                            [LEFT] + [CENTER] * months, ["General"] + ["0%"] * months)
    ws.conditional_formatting.add(
        f"F{table_row + 1}:{get_column_letter(5 + months)}{last_trend}",
        ColorScaleRule(start_type="num", start_value=0, start_color="F8D7D5",
                       mid_type="num", mid_value=0.6, mid_color="FFFFFF",
                       end_type="num", end_value=1, end_color="D5F0E3"))

    chart_row = max(last_scores, last_trend) + 2
    _section(ws, chart_row, 2, "Monthly Trend")
    _add_trend_chart(ws, table_row, last_trend, 5, 5 + months, chart_row, last_col)
    ws.page_setup.fitToHeight = 1  # the dashboard prints on one page


# --- Visibility and Top Performers -------------------------------------------------

def _build_visibility_sheet(wb, line_details, line_totals, month_name, year):
    ws = wb.create_sheet("Visibility")
    headers = ["Origin Country", "Destination PO", "Reflected Lines", "Approved", "Rejected"]
    first = FIRST_CONTENT_ROW
    _frame(ws, "Visibility", f"{month_name} {year}", 6, CYAN, print_title_rows=f"{first}:{first}")

    fields = ["country", "dest_po_count", "reflected_lines", "approved", "rejected"]
    last = _add_table(
        ws, "Table9", first, 2, headers, [[item[f] for f in fields] for item in line_details],
        [LEFT] + [RIGHT] * 4, ["General"] + ["#,##0"] * 4,
        totals={"Origin Country": ("label", "Total"), **{h: ("sum", 109) for h in headers[1:]}},
        widths=[24, 17, 17, 17, 17],
    )
    _data_bars(ws, f"D{first + 1}:D{last - 1}")
    ws.freeze_panes = f"A{first + 1}"


def _build_top_performers_sheet(wb, top_suppliers, month_name, year):
    ws = wb.create_sheet("Top Performers")
    headers = ["#", "Origin", "Supplier", "No. of Factories", "Destination PO",
               "Reflected Lines", "Compliance Score"]
    first = FIRST_CONTENT_ROW
    _frame(ws, "Top Suppliers", f"{month_name} {year}", 8, CYAN, print_title_rows=f"{first}:{first}")

    rows = [[s["sl"], s["origin_countries"], s["supplier"], s["factory_count"], s["dest_po_count"],
             s["reflected_lines"], s["compliance_rate"] / 100.0] for s in top_suppliers]
    last = _add_table(ws, "Table8", first, 2, headers, rows,
                      [CENTER, LEFT, LEFT, RIGHT, RIGHT, RIGHT, RIGHT],
                      ["0", "General", "General", "#,##0", "#,##0", "#,##0", "0%"],
                      widths=[6, 24, 58, 15, 15, 15, 17])
    _data_bars(ws, f"G{first + 1}:G{last}")
    ws.freeze_panes = f"A{first + 1}"


# --- Follow-Up Required sheet ---------------------------------------------------

FOLLOW_UP_HEADERS = ["Sl", "Origin Country", "Supplier Name", "No of Factories",
                     "Destination PO Qty", "Reflected Lines", "Compliance Score", "Email"]


def _build_follow_up_required_sheet(wb, suppliers_below, email_map, month_label):
    ws = wb.create_sheet("Follow-Up Required")
    first = FIRST_CONTENT_ROW
    _frame(ws, "Follow-Up Required", f"Avg. Compliance <40% – Last 3 Months · {month_label}",
           9, ALERT, accent=ALERT, print_title_rows=f"{first}:{first}")

    rows = []
    for supplier in suppliers_below:
        rate = supplier.get("avg_3month")
        if rate is None:
            rate = supplier.get("compliance_rate", 0)
        rows.append([supplier["sl"], supplier["origin_country"], supplier["supplier"],
                     supplier["factory_count"], supplier["dest_po_count"], supplier["reflected_lines"],
                     rate / 100.0, email_map.get(supplier["supplier"].strip().lower(), "")])
    last = _add_table(ws, "Table6", first, 2, FOLLOW_UP_HEADERS, rows,
                      [CENTER, LEFT, LEFT, RIGHT, RIGHT, RIGHT, RIGHT, LEFT],
                      ["0", "General", "General", "#,##0", "#,##0", "#,##0", "0%", "General"],
                      widths=[6, 22, 46, 15, 17, 15, 17, 40])

    for row in range(first + 1, last + 1):
        ws.cell(row=row, column=8).font = Font(bold=True, size=10, color=LOW_TEXT)
        email = ws.cell(row=row, column=9)
        if email.value:
            email.hyperlink = "mailto:" + email.value.replace(" ", "")
            email.font = Font(size=10, color=LINK, underline="single")
    ws.freeze_panes = f"A{first + 1}"


# --- Yearly Performance sheet ---------------------------------------------------

YEAR_BAND_ROW = FIRST_CONTENT_ROW
HEADER_ROW = YEAR_BAND_ROW + 1
FIRST_DATA_ROW = HEADER_ROW + 1


def _build_yearly_performance_sheet(wb, supplier_trend, month_labels, year):
    ws = wb.create_sheet("Yearly Performance")
    num_months = len(month_labels)
    first_month_col = 4
    last_month_col = first_month_col + num_months - 1
    total_col = last_month_col + 1
    last_month_letter = get_column_letter(last_month_col)

    _frame(ws, "Suppliers Yearly Performance",
           f"January {year} to {chart_end_caption(month_labels, year)}",
           total_col, NAVY, print_title_rows=f"{YEAR_BAND_ROW}:{HEADER_ROW}")
    ws.column_dimensions["B"].width = 6
    ws.column_dimensions["C"].width = 66
    for col in range(first_month_col, total_col):
        ws.column_dimensions[get_column_letter(col)].width = 10
    ws.column_dimensions[get_column_letter(total_col)].width = 11

    ws.merge_cells(start_row=YEAR_BAND_ROW, start_column=first_month_col,
                   end_row=YEAR_BAND_ROW, end_column=last_month_col)
    band = ws.cell(row=YEAR_BAND_ROW, column=first_month_col, value=year)
    band.font, band.alignment = Font(bold=True, size=10, color="FFFFFF"), CENTER
    for col in range(first_month_col, last_month_col + 1):
        ws.cell(row=YEAR_BAND_ROW, column=col).fill = _fill(CYAN)

    for j, label in enumerate(["#", "Supplier Name"] + list(month_labels) + ["Total"]):
        cell = ws.cell(row=HEADER_ROW, column=2 + j, value=label)
        cell.font, cell.fill = HEADER_FONT, _fill(NAVY)
        cell.alignment = LEFT if j == 1 else CENTER
    ws.row_dimensions[HEADER_ROW].height = 24

    hairline = Side(style="thin", color=LINE)
    for idx, supplier in enumerate(supplier_trend, start=1):
        row = HEADER_ROW + idx
        ws.row_dimensions[row].height = 18
        ws.cell(row=row, column=2, value=idx).alignment = CENTER
        ws.cell(row=row, column=3, value=supplier["supplier"]).alignment = LEFT

        for i, rate in enumerate(supplier["rates"]):
            # A month with no data stays genuinely empty, so AVERAGE skips it.
            cell = ws.cell(row=row, column=first_month_col + i, value=None if rate is None else rate / 100.0)
            cell.number_format, cell.alignment = "0.0%", CENTER

        total = ws.cell(row=row, column=total_col,
                        value=f'=IFERROR(AVERAGE({get_column_letter(first_month_col)}{row}'
                              f':{last_month_letter}{row}),"")')
        total.number_format, total.alignment = "0.0%", CENTER

        for col in range(2, total_col + 1):
            cell = ws.cell(row=row, column=col)
            cell.border = Border(bottom=hairline)
            cell.font = TOTAL_FONT if col == total_col else BODY_FONT
            if col == total_col:
                cell.fill = _fill(TINT)
            elif idx % 2 == 0:
                cell.fill = _fill(STRIPE)

    last_row = HEADER_ROW + len(supplier_trend)
    rates = f"{get_column_letter(first_month_col)}{FIRST_DATA_ROW}:{get_column_letter(total_col)}{last_row}"
    # Blank months (no data) stay unshaded, so each rule checks ISNUMBER before the threshold.
    top_left = f"{get_column_letter(first_month_col)}{FIRST_DATA_ROW}"
    ws.conditional_formatting.add(rates, FormulaRule(
        formula=[f"AND(ISNUMBER({top_left}),{top_left}<0.4)"],
        fill=_fill(LOW_FILL), font=Font(bold=True, color=LOW_TEXT)))
    ws.conditional_formatting.add(rates, FormulaRule(
        formula=[f"AND(ISNUMBER({top_left}),{top_left}>=0.4,{top_left}<0.6)"],
        fill=_fill(MID_FILL), font=Font(color=MID_TEXT)))

    ws.auto_filter.ref = f"B{HEADER_ROW}:{get_column_letter(total_col)}{last_row}"
    ws.freeze_panes = f"D{FIRST_DATA_ROW}"


def chart_end_caption(month_labels, year):
    """"July 2026" from the last chart label ("Jul '26"); just the year if unparseable."""
    try:
        m_abbr, yy = month_labels[-1].split(" '")
        return f"{calendar.month_name[list(calendar.month_abbr).index(m_abbr)]} 20{int(yy)}"
    except (IndexError, ValueError):
        return f"{year}"

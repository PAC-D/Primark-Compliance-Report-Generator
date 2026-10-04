import calendar

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

BAND_FILL = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
YEAR_FILL = PatternFill(start_color="4A5568", end_color="4A5568", fill_type="solid")
HEADER_FILL = PatternFill(start_color="1B2838", end_color="1B2838", fill_type="solid")

CENTER_MIDDLE = Alignment(horizontal="center", vertical="center")
CENTER = Alignment(horizontal="center")
LEFT = Alignment(horizontal="left")

# Widths carried over from the reference workbook; extra months fall back to
# the width used by most month columns.
MONTH_WIDTHS = [10.45, 10.63, 11.0, 10.45, 11.36, 10.45, 13.63]
DEFAULT_MONTH_WIDTH = 10.45

YEAR_BAND_ROW = 6
HEADER_ROW = 7
FIRST_DATA_ROW = 8


def _make_thin_border():
    thin = Side(style='thin')
    return Border(left=thin, right=thin, top=thin, bottom=thin)


def _build_yearly_performance_sheet(wb, supplier_trend, month_labels, year):
    ws = wb.create_sheet("Yearly Performance")
    ws.sheet_view.showGridLines = False

    num_months = len(month_labels)
    last_month_col = 2 + num_months
    total_col = last_month_col + 1
    last_month_letter = get_column_letter(last_month_col)

    title_ref = f"A1:{last_month_letter}1"
    ws.merge_cells(title_ref)
    ws["A1"] = (f"Suppliers Yearly Performance – January {year} "
                f"to {chart_end_caption(month_labels, year)}")
    ws["A1"].font = Font(bold=True, size=13, color="1F4E79")
    ws["A1"].alignment = CENTER_MIDDLE
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
        cell.fill = HEADER_FILL
        cell.alignment = CENTER_MIDDLE
        cell.border = _make_thin_border()

    ws.column_dimensions["A"].width = 6.45
    ws.column_dimensions["B"].width = 81.36
    for i in range(num_months):
        width = MONTH_WIDTHS[i] if i < len(MONTH_WIDTHS) else DEFAULT_MONTH_WIDTH
        ws.column_dimensions[get_column_letter(3 + i)].width = width
    ws.column_dimensions[get_column_letter(total_col)].width = 7.82

    for idx, supplier in enumerate(supplier_trend, start=1):
        row = HEADER_ROW + idx
        banded = idx % 2 == 0

        index_cell = ws.cell(row=row, column=1, value=idx)
        index_cell.alignment = CENTER

        name_cell = ws.cell(row=row, column=2, value=supplier["supplier"])
        name_cell.alignment = LEFT

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
            cell.border = _make_thin_border()
            if banded:
                cell.fill = BAND_FILL

    last_row = HEADER_ROW + len(supplier_trend)
    ws.auto_filter.ref = f"A{HEADER_ROW}:{get_column_letter(total_col)}{last_row}"
    ws.freeze_panes = f"A{FIRST_DATA_ROW}"


def chart_end_caption(month_labels, year):
    if not month_labels:
        return f"{year}"
    last_label = month_labels[-1]
    try:
        m_abbr, yy = last_label.split(" '")
        month = next(i for i, name in enumerate(MONTH_ABBR, 1) if name == m_abbr)
        return f"{calendar.month_name[month]} 20{int(yy)}"
    except (ValueError, StopIteration):
        return f"{year}"

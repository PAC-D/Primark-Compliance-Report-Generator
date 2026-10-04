from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableColumn, TableStyleInfo

HEADER_FILL = PatternFill(start_color="156082", end_color="156082", fill_type="solid")
HEADER_FONT = Font(bold=True, size=10, color="FFFFFF")

CENTER = Alignment(horizontal="center")
CENTER_MIDDLE = Alignment(horizontal="center", vertical="center")

HEADERS = ["Sl ", "Origin Country ", "Supplier Name ", "No of Factories ",
           "Destination PO Qty ", "Reflected Lines ", "Compliance Score ", "Email "]

# Header cells that are explicitly centred; the rest keep the default alignment.
CENTERED_HEADERS = {2, 4, 5, 6, 7}

WIDTHS = {"A": 5.0, "B": 22.0, "C": 45.0, "D": 17.45,
          "E": 16.63, "F": 17.18, "G": 19.63, "H": 92.82}


def build_follow_up_required_sheet(wb, suppliers_below, email_map=None,
                                   month_label=None):
    if email_map is None:
        email_map = {}
    ws = wb.create_sheet("Follow-Up Required")
    ws.sheet_view.showGridLines = False

    # get_suppliers_below_threshold() does not carry a month, so the caller
    # passes it in; the per-row key is only a fallback for older callers.
    if month_label is None and suppliers_below:
        month_label = suppliers_below[0].get("month_label")

    title = "Follow-Up Required (Avg. Compliance <40% – Last 3 Months)"
    if month_label:
        title = f"{title} – {month_label}"

    ws.merge_cells("A1:H1")
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=13, color="1F4E79")
    ws["A1"].alignment = CENTER_MIDDLE
    ws.row_dimensions[1].height = 17.0

    for col, label in enumerate(HEADERS, 1):
        cell = ws.cell(row=2, column=col, value=label)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        if col in CENTERED_HEADERS:
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
    columns = [TableColumn(id=i, name=label) for i, label in enumerate(HEADERS, 1)]
    table = Table(displayName="Table6", ref=f"A2:H{last_row}", tableColumns=columns)
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleLight9", showRowStripes=True, showColumnStripes=False,
        showFirstColumn=False, showLastColumn=False,
    )
    ws.add_table(table)

    for letter, width in WIDTHS.items():
        ws.column_dimensions[letter].width = width
    ws.freeze_panes = "A3"


# Kept for backward-compat with any external callers; routes to new name+layout.
def _build_suppliers_below_threshold_sheet(*args, **kwargs):
    return build_follow_up_required_sheet(*args, **kwargs)

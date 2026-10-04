"""Structural fingerprints for generated workbooks.

Compares what the renderer *controls* - values, number formats, explicit
fonts/fills/alignment, merges, freeze panes, column widths, table definitions
and chart configuration.

Theme-driven colours are deliberately normalised away: Excel resolves table
styles at save time, so a workbook written by openpyxl can never carry the same
theme/tint metadata as one round-tripped through Excel. Only colours the
renderer sets explicitly are compared.
"""

def _rgb(colour):
    """Explicit RGB of a colour, or None for theme/indexed/absent colours.

    Normalised to six hex digits: openpyxl writes a colour built from "F9FAFB"
    as 00F9FAFB, where Excel round-trips the same colour as FFF9FAFB. The alpha
    channel carries no meaning here, so it is dropped.
    """
    if colour is None:
        return None
    if getattr(colour, "type", None) != "rgb":
        return None
    rgb = getattr(colour, "rgb", None)
    if not isinstance(rgb, str):
        return None
    if len(rgb) == 8:
        rgb = rgb[2:]
    # Excel writes black as an explicit 000000; openpyxl leaves the default
    # font colourless. Treat both as "no explicit colour".
    if rgb == "000000":
        return None
    return rgb.upper()


def _fill(cell):
    if cell.fill is None or cell.fill.fill_type is None:
        return None
    return _rgb(cell.fill.start_color)


def _value(cell):
    v = cell.value
    if isinstance(v, float):
        return round(v, 10)
    return v


def cell_fingerprint(cell):
    return {
        "value": _value(cell),
        "number_format": cell.number_format,
        "bold": bool(cell.font.bold),
        "size": cell.font.size,
        "font": _rgb(cell.font.color),
        "fill": _fill(cell),
        "halign": cell.alignment.horizontal,
    }


def table_fingerprint(table):
    style = table.tableStyleInfo
    return {
        "ref": table.ref,
        "style": style.name if style else None,
        "row_stripes": bool(style.showRowStripes) if style else None,
        "totals_row_count": table.totalsRowCount,
        "columns": [
            {
                "name": col.name,
                "totals_function": col.totalsRowFunction,
                "totals_label": col.totalsRowLabel,
            }
            for col in table.tableColumns
        ],
    }


def _ref(source):
    """Normalise a chart cell reference.

    openpyxl writes 'Summary'!D29 where Excel round-trips Summary!$D$29. The
    quoting and the absolute markers carry no meaning for a chart reference, so
    both are stripped before comparing.
    """
    if source is None:
        return None
    for holder in ("strRef", "numRef"):
        ref = getattr(source, holder, None)
        if ref is not None and ref.f:
            return ref.f.replace("'", "").replace("$", "")
    return None


def chart_fingerprint(chart):
    anchor = chart.anchor
    frm = getattr(anchor, "_from", None)
    to = getattr(anchor, "to", None)

    title = None
    try:
        para = chart.title.tx.rich.p[0]
        title = "".join(run.t for run in (para.r or []) if run.t)
    except (AttributeError, IndexError, TypeError):
        pass

    def axis_title(axis):
        try:
            para = axis.title.tx.rich.p[0]
            return "".join(run.t for run in (para.r or []) if run.t)
        except (AttributeError, IndexError, TypeError):
            return None

    return {
        "type": type(chart).__name__,
        "title": title,
        "x_axis_title": axis_title(chart.x_axis),
        "y_axis_title": axis_title(chart.y_axis),
        "y_axis_number_format": (
            (chart.y_axis.numFmt.formatCode, bool(chart.y_axis.numFmt.sourceLinked))
            if chart.y_axis.numFmt is not None else None
        ),
        "anchor_from": (frm.col, frm.row) if frm else None,
        "anchor_to": (to.col, to.row) if to else None,
        "grouping": getattr(chart, "grouping", None),
        "gap_width": getattr(chart, "gapWidth", None),
        "overlap": getattr(chart, "overlap", None),
        "legend_position": chart.legend.position if chart.legend else None,
        "series_count": len(chart.series),
        "series_titles": [_ref(s.tx) for s in chart.series],
        "series_values": [_ref(s.val) for s in chart.series],
        "categories": [_ref(s.cat) for s in chart.series],
        "show_values": [
            bool(s.dLbls.showVal) if s.dLbls is not None else False
            for s in chart.series
        ],
        # Excel treats an omitted data-label flag as ON, so an absent flag is a
        # real difference from an explicit False - record each one as written.
        "label_flags": [
            None if s.dLbls is None else {
                flag: getattr(s.dLbls, flag)
                for flag in ("showVal", "showSerName", "showCatName",
                             "showLegendKey", "showPercent", "showBubbleSize")
            }
            for s in chart.series
        ],
        "category_ref_type": [
            None if s.cat is None else
            ("strRef" if s.cat.strRef is not None else
             "numRef" if s.cat.numRef is not None else None)
            for s in chart.series
        ],
        "axes_deleted": (chart.x_axis.delete, chart.y_axis.delete),
        "major_gridlines": (chart.x_axis.majorGridlines is not None,
                            chart.y_axis.majorGridlines is not None),
    }


def sheet_fingerprint(ws, max_row=None, max_col=None):
    max_row = max_row or ws.max_row
    max_col = max_col or ws.max_column

    cells = {}
    for row in ws.iter_rows(min_row=1, max_row=max_row, max_col=max_col):
        for cell in row:
            if cell.value is None and _fill(cell) is None:
                continue
            cells[cell.coordinate] = cell_fingerprint(cell)

    return {
        "merged": sorted(str(r) for r in ws.merged_cells.ranges),
        "freeze_panes": ws.freeze_panes,
        # Absent in the XML means "shown"; only an explicit False hides them.
        "show_gridlines": ws.sheet_view.showGridLines is not False,
        "column_widths": {
            letter: round(dim.width, 2)
            for letter, dim in ws.column_dimensions.items()
            if dim.width is not None
        },
        "row_heights": {
            idx: dim.height
            for idx, dim in ws.row_dimensions.items()
            if dim.height is not None
        },
        "auto_filter": ws.auto_filter.ref,
        # TableList.items() yields refs, not Table objects; index to get the object.
        "tables": {name: table_fingerprint(ws.tables[name]) for name in ws.tables},
        "charts": [chart_fingerprint(c) for c in ws._charts],
        "cells": cells,
    }


def diff_fingerprints(expected, actual, path=""):
    """Flat list of human-readable differences between two fingerprints."""
    diffs = []

    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            sub = f"{path}.{key}" if path else str(key)
            if key not in expected:
                diffs.append(f"{sub}: unexpected {actual[key]!r}")
            elif key not in actual:
                diffs.append(f"{sub}: missing (expected {expected[key]!r})")
            else:
                diffs.extend(diff_fingerprints(expected[key], actual[key], sub))
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            diffs.append(f"{path}: length {len(actual)}, expected {len(expected)}")
        else:
            for i, (e, a) in enumerate(zip(expected, actual)):
                diffs.extend(diff_fingerprints(e, a, f"{path}[{i}]"))
    elif expected != actual:
        diffs.append(f"{path}: {actual!r}, expected {expected!r}")

    return diffs

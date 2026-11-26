"""Data extracts built from raw_data: one workbook of the whole month, one per
supplier split by region, or a single supplier's month as bytes.

Files go to output/<YYYY_Month>/Supplier_Data/.
"""

import calendar
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from tps import config
from tps.common import next_month_start, normalise_supplier, report_region, safe_filename
from tps.db import get_engine
from tps.ingest import COLUMN_RENAME

_SOURCE_HEADERS = {
    **{db: header for header, db in COLUMN_RENAME.items()},
    "compliance_status": "Compliance Status",
}
# Derived or internal columns the team doesn't want in the workbooks.
_NOT_EXPORTED = ["id", "source_file", "carton_type", "cbm", "density"]


def month_frame(report_month: date, supplier: str | None = None) -> pd.DataFrame:
    """raw_data rows handed over in the month (optionally one supplier's), under
    the source files' own headers plus the derived columns."""
    sql = "SELECT * FROM raw_data WHERE handover_date >= :start AND handover_date < :end"
    params = {"start": report_month, "end": next_month_start(report_month)}
    if supplier is not None:
        sql += " AND supplier = :supplier"
        params["supplier"] = supplier
    df = pd.read_sql(text(sql + " ORDER BY handover_date, updated_date"), get_engine(), params=params)
    # Excel has no timezones. The TIMESTAMPTZ columns arrive as object dtype when their
    # rows carry different UTC offsets (summer/winter time), so convert them by name.
    for col in ("updated_date", "approved_date"):
        if col in df:
            df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None)
    return df.drop(columns=_NOT_EXPORTED, errors="ignore").rename(columns=_SOURCE_HEADERS)


def _month_dir(year: int, month: int) -> Path:
    path = config.month_folder(date(year, month, 1)) / config.SUPPLIER_DATA
    path.mkdir(parents=True, exist_ok=True)
    return path


def monthly_path(year: int, month: int) -> Path:
    """Where extract_monthly writes the month's combined workbook."""
    return (config.month_folder(date(year, month, 1)) / config.SUPPLIER_DATA
            / f"All_Suppliers_{calendar.month_abbr[month]}_{year}.xlsx")


def _rows(year: int, month: int) -> pd.DataFrame:
    df = month_frame(date(year, month, 1))
    if df.empty:
        raise FileNotFoundError(f"No data for {calendar.month_abbr[month]} {year}")
    return df


def extract_monthly(year: int, month: int) -> Path:
    """All suppliers' rows for the month in a single workbook."""
    combined = _rows(year, month)
    _month_dir(year, month)
    output_path = monthly_path(year, month)
    combined.to_excel(output_path, index=False)
    return output_path


def extract_by_supplier(year: int, month: int) -> Path:
    """One workbook per supplier, under 'BD_Region/' or 'CN_Region/'."""
    combined = _rows(year, month)
    combined["Supplier"] = combined["Supplier"].apply(
        lambda x: normalise_supplier(str(x)) if pd.notna(x) else x)

    base_output = _month_dir(year, month)
    month_name = calendar.month_name[month]
    for supplier, group in combined.groupby("Supplier"):
        region_dir = base_output / report_region(c for c in group["Origin Country"].unique() if pd.notna(c))
        region_dir.mkdir(exist_ok=True)
        group.to_excel(region_dir / f"{safe_filename(supplier)}_{month_name}_{year}.xlsx", index=False)
    return base_output


def supplier_workbook(supplier: str, report_month: date) -> bytes:
    """One supplier's month as .xlsx bytes."""
    buffer = BytesIO()
    month_frame(report_month, supplier).to_excel(buffer, index=False)
    return buffer.getvalue()


def supplier_data_zip(suppliers: list[str], report_month: date) -> bytes | None:
    """A zip of each supplier's month workbook (as supplier_workbook); None when none has data."""
    buffer, added = BytesIO(), 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for supplier in dict.fromkeys(suppliers):
            df = month_frame(report_month, supplier)
            if df.empty:
                continue
            sheet = BytesIO()
            df.to_excel(sheet, index=False)
            z.writestr(f"{safe_filename(supplier)}_{report_month:%B_%Y}.xlsx", sheet.getvalue())
            added += 1
    return buffer.getvalue() if added else None

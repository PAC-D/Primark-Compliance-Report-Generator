from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from tps import extract


def _frame(supplier, country):
    return pd.DataFrame({"Supplier": [supplier], "Origin Country": [country]})


@pytest.fixture
def out(tmp_path, monkeypatch):
    monkeypatch.setattr("tps.config.OUTPUT_DIR", tmp_path / "output")
    return tmp_path / "output" / "2026_May" / "Supplier_Data"


def _month(supplier, country):
    return patch("tps.extract.month_frame", return_value=_frame(supplier, country))


def test_month_frame_restores_source_headers():
    rows = pd.DataFrame({"id": [1], "supplier": ["A"], "handover_date": [date(2026, 5, 3)],
                         "packaging_status": ["Approved"], "compliance_status": ["Compliant"],
                         "cbm": [0.5], "density": [40.0], "carton_type": ["Custom"],
                         "source_file": ["f.xlsx"]})
    with patch("tps.extract.get_engine"), patch("tps.extract.pd.read_sql", return_value=rows):
        df = extract.month_frame(date(2026, 5, 1))
    assert list(df.columns) == ["Supplier", "Current Handover Date",
                                "Packaging Confirmation Status", "Compliance Status"]


def test_supplier_filename_uses_full_month_name(out):
    with _month("Test Supplier Ltd", "Bangladesh"):
        extract.extract_by_supplier(2026, 5)
    assert [p.name for p in (out / "BD_Region").glob("*.xlsx")] == ["Test Supplier Ltd_May_2026.xlsx"]


def test_extract_by_supplier_splits_regions(out):
    with _month("WEIHAI BETTEX INTERNATIONAL TRADING CO., LTD", "China"):
        extract.extract_by_supplier(2026, 5)
    assert [p.name for p in (out / "CN_Region").glob("*.xlsx")] == ["BETTEX (HK) LIMITED (80243)_May_2026.xlsx"]


def test_monthly_writes_one_combined_workbook(out):
    with _month("Test Supplier Ltd", "Bangladesh"):
        path = extract.extract_monthly(2026, 5)
    assert path == out / "All_Suppliers_May_2026.xlsx" == extract.monthly_path(2026, 5)
    assert pd.read_excel(path)["Supplier"].tolist() == ["Test Supplier Ltd"]


@pytest.mark.parametrize("fn", [extract.extract_monthly, extract.extract_by_supplier])
def test_extract_empty_month_raises(out, fn):
    with patch("tps.extract.month_frame", return_value=pd.DataFrame()):
        with pytest.raises(FileNotFoundError, match="No data for Aug 2026"):
            fn(2026, 8)


def test_supplier_workbook_is_xlsx():
    with _month("A", "China"):
        assert extract.supplier_workbook("A", date(2026, 5, 1)).startswith(b"PK")


def _tz_rows():
    return pd.DataFrame({"supplier": ["A"], "origin_country": ["China"],
                         "handover_date": [date(2026, 5, 3)],
                         "updated_date": pd.to_datetime(["2026-05-01 10:00"]).tz_localize("UTC")})


def test_tz_aware_columns_still_export_to_excel(out):
    with patch("tps.extract.get_engine"), patch("tps.extract.pd.read_sql", return_value=_tz_rows()):
        assert extract.supplier_workbook("A", date(2026, 5, 1)).startswith(b"PK")
        path = extract.extract_monthly(2026, 5)
    assert pd.read_excel(path)["Updated Date"].dt.tz is None


def test_mixed_utc_offsets_export_to_excel(out):
    # Real rows: TIMESTAMPTZ values with summer and winter offsets come back as object dtype.
    from datetime import datetime, timedelta, timezone
    rows = pd.DataFrame({
        "supplier": ["A", "A"], "handover_date": [date(2026, 10, 2)] * 2,
        "updated_date": [datetime(2026, 8, 6, 4, 34, tzinfo=timezone(timedelta(hours=-7))),
                         datetime(2026, 11, 2, 9, 0, tzinfo=timezone(timedelta(hours=-8)))],
        "approved_date": [None, datetime(2026, 11, 2, 9, 0, tzinfo=timezone(timedelta(hours=-8)))],
    })
    assert rows["updated_date"].dtype == object
    with patch("tps.extract.get_engine"), patch("tps.extract.pd.read_sql", return_value=rows):
        df = extract.month_frame(date(2026, 10, 1))
        assert extract.supplier_workbook("A", date(2026, 10, 1)).startswith(b"PK")
    assert df["Updated Date"].dt.tz is None
    assert df["Updated Date"].iloc[0] == pd.Timestamp("2026-08-06 11:34")  # stored as UTC
    assert pd.isna(df["Approved Date"].iloc[0])


def test_month_frame_queries_the_month_range_and_optional_supplier():
    with patch("tps.extract.get_engine"),          patch("tps.extract.pd.read_sql", return_value=pd.DataFrame()) as read_sql:
        extract.month_frame(date(2026, 12, 1))
        extract.month_frame(date(2026, 12, 1), "ACME")
    (all_sql,), all_kw = read_sql.call_args_list[0].args[:1], read_sql.call_args_list[0].kwargs
    (one_sql,), one_kw = read_sql.call_args_list[1].args[:1], read_sql.call_args_list[1].kwargs
    assert all_kw["params"] == {"start": date(2026, 12, 1), "end": date(2027, 1, 1)}
    assert "supplier = :supplier" not in str(all_sql)
    assert one_kw["params"] == {"start": date(2026, 12, 1), "end": date(2027, 1, 1), "supplier": "ACME"}
    assert "supplier = :supplier" in str(one_sql)


def test_supplier_data_zip_skips_suppliers_without_data():
    import zipfile
    from io import BytesIO
    frames = {"A & B": pd.DataFrame({"Supplier": ["A & B"]}), "C": pd.DataFrame()}
    with patch("tps.extract.month_frame", side_effect=lambda month, s: frames[s]):
        content = extract.supplier_data_zip(["A & B", "C", "A & B"], date(2026, 5, 1))
        assert zipfile.ZipFile(BytesIO(content)).namelist() == ["A & B_May_2026.xlsx"]
        assert extract.supplier_data_zip(["C"], date(2026, 5, 1)) is None

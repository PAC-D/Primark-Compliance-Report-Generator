import pandas as pd

from tps import extract


def _source_file(tmp_path, monkeypatch, supplier, country):
    """One bi-weekly source file for May 2026 in a temp data/ folder."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame({"Supplier": [supplier], "Origin Country": [country]}).to_excel(
        data_dir / "Multi Search (Packaging Management)_2026_May_1-15.xlsx", index=False
    )
    monkeypatch.setattr("tps.config.DATA_DIR", data_dir)
    monkeypatch.setattr("tps.config.OUTPUT_DIR", tmp_path / "output")
    return tmp_path / "output" / "2026_May" / "Supplier_Data"


def test_supplier_filename_uses_full_month_name(tmp_path, monkeypatch):
    """Same 'Month_Year' format as the Summary_Report_<Month>_<Year> output."""
    out = _source_file(tmp_path, monkeypatch, "Test Supplier Ltd", "Bangladesh")

    extract.extract_by_supplier(2026, 5)

    assert [p.name for p in (out / "BD_Region").glob("*.xlsx")] == ["Test Supplier Ltd_May_2026.xlsx"]


def test_supplier_name_normalisation_is_applied(tmp_path, monkeypatch):
    """Renamed suppliers get the canonical name the reports use."""
    out = _source_file(tmp_path, monkeypatch, "WEIHAI BETTEX INTERNATIONAL TRADING CO., LTD", "China")

    extract.extract_by_supplier(2026, 5)

    assert [p.name for p in (out / "CN_Region").glob("*.xlsx")] == ["BETTEX (HK) LIMITED (80243)_May_2026.xlsx"]


def test_monthly_writes_one_combined_workbook(tmp_path, monkeypatch):
    out = _source_file(tmp_path, monkeypatch, "Test Supplier Ltd", "Bangladesh")

    path = extract.extract_monthly(2026, 5)

    assert path == out / "All_Suppliers_May_2026.xlsx"
    assert pd.read_excel(path)["Supplier"].tolist() == ["Test Supplier Ltd"]

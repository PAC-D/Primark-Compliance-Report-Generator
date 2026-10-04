import pandas as pd

from tps import extract as esd


def _source_file(tmp_path, monkeypatch, supplier, country):
    """One bi-weekly source file for May 2026 in a temp data/ folder."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame({"Supplier": [supplier], "Origin Country": [country]}).to_excel(
        data_dir / "Multi Search (Packaging Management)_2026_May_1-15.xlsx", index=False
    )
    monkeypatch.setattr(esd, "DATA_DIR", data_dir)
    monkeypatch.setattr(esd, "OUTPUT_DIR", tmp_path / "output")


def test_filename_uses_full_month_name_matching_tps_pipeline(tmp_path, monkeypatch):
    """Per-supplier filenames must use the same 'Month_Year' format as
    tps-pipeline's Summary_Report_<Month>_<Year> outputs, not zero-padded
    numeric months."""
    _source_file(tmp_path, monkeypatch, "Test Supplier Ltd", "Bangladesh")

    esd.extract_supplier_data(2026, 5)

    produced = list((tmp_path / "output" / "Data_May_2026" / "BD Region").glob("*.xlsx"))
    assert [p.name for p in produced] == ["Test Supplier Ltd_May_2026.xlsx"]


def test_supplier_name_normalisation_is_applied(tmp_path, monkeypatch):
    """Aliased/renamed supplier names must be normalised to the same
    canonical name tps-pipeline uses, so per-supplier files match reports."""
    _source_file(tmp_path, monkeypatch, "WEIHAI BETTEX INTERNATIONAL TRADING CO., LTD", "China")

    esd.extract_supplier_data(2026, 5)

    produced = list((tmp_path / "output" / "Data_May_2026" / "CN Region").glob("*.xlsx"))
    assert [p.name for p in produced] == ["BETTEX (HK) LIMITED (80243)_May_2026.xlsx"]

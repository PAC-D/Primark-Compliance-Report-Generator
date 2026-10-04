import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import extract_supplier_data as esd


def test_filename_uses_full_month_name_matching_tps_pipeline(tmp_path, monkeypatch):
    """Per-supplier filenames must use the same 'Month_Year' format as
    tps-pipeline's Summary_Report_<Month>_<Year> outputs, not zero-padded
    numeric months."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    df = pd.DataFrame({
        "Supplier": ["Test Supplier Ltd"],
        "Origin Country": ["Bangladesh"],
    })
    src_file = data_dir / "Multi Search (Packaging Management)_2026_May_1-15.xlsx"
    df.to_excel(src_file, index=False)

    monkeypatch.setattr(esd, "get_data_folder", lambda: data_dir)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(esd, "__file__", str(tmp_path / "extract_supplier_data.py"))

    esd.extract_supplier_data(2026, 5)

    produced = list((tmp_path / "output" / "Data_May_2026" / "BD Region").glob("*.xlsx"))
    assert len(produced) == 1
    assert produced[0].name == "Test Supplier Ltd_May_2026.xlsx"


def test_supplier_name_normalisation_is_applied(tmp_path, monkeypatch):
    """Aliased/renamed supplier names must be normalised to the same
    canonical name tps-pipeline uses, so per-supplier files match reports."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    df = pd.DataFrame({
        "Supplier": ["WEIHAI BETTEX INTERNATIONAL TRADING CO., LTD"],
        "Origin Country": ["China"],
    })
    src_file = data_dir / "Multi Search (Packaging Management)_2026_May_1-15.xlsx"
    df.to_excel(src_file, index=False)

    monkeypatch.setattr(esd, "get_data_folder", lambda: data_dir)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(esd, "__file__", str(tmp_path / "extract_supplier_data.py"))

    esd.extract_supplier_data(2026, 5)

    produced = list((tmp_path / "output" / "Data_May_2026" / "CN Region").glob("*.xlsx"))
    assert len(produced) == 1
    assert produced[0].name == "BETTEX (HK) LIMITED (80243)_May_2026.xlsx"

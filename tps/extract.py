"""Re-slice the raw bi-weekly source files in data/ without touching the database.

    python -m tps.extract monthly    one workbook with every row for a month
    python -m tps.extract supplier   one workbook per supplier, split by region

Both write to output/Data_<Month>_<Year>/.
"""

import argparse
import calendar
import sys
from pathlib import Path

import pandas as pd

from tps.common import ask_report_month, normalise_supplier, report_region, safe_filename
from tps.config import DATA_DIR, OUTPUT_DIR


def load_month_files(year: int, month: int) -> pd.DataFrame:
    """Every bi-weekly source file for the month, concatenated."""
    mon = calendar.month_abbr[month]
    files = list(DATA_DIR.glob(f"*_{year}_{mon}_*.xlsx"))
    if not files:
        raise FileNotFoundError(f"No files found for {mon}/{year} in {DATA_DIR}")
    print(f"Found {len(files)} file(s) for {month:02d}/{year}")

    dfs = []
    for f in files:
        df = pd.read_excel(f)
        dfs.append(df)
        print(f"Loaded: {f.name} ({len(df)} rows)")
    return pd.concat(dfs, ignore_index=True)


def _month_dir(year: int, month: int) -> Path:
    path = OUTPUT_DIR / f"Data_{calendar.month_name[month]}_{year}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def extract_monthly(year: int, month: int) -> Path:
    """All suppliers' rows for the month in a single workbook."""
    combined = load_month_files(year, month)
    print(f"Total combined rows: {len(combined)}")
    print(f"Unique suppliers: {combined['Supplier'].nunique()}")

    output_path = _month_dir(year, month) / f"All_Suppliers_{calendar.month_abbr[month]}_{year}.xlsx"
    combined.to_excel(output_path, index=False)
    print(f"\nExtraction complete! Single file saved to: {output_path}")
    return output_path


def extract_by_supplier(year: int, month: int) -> Path:
    """One workbook per supplier, under 'BD Region/' or 'CN Region/'."""
    combined = load_month_files(year, month)
    combined["Supplier"] = combined["Supplier"].apply(
        lambda x: normalise_supplier(str(x)) if pd.notna(x) else x)
    print(f"Total combined rows: {len(combined)}")
    print(f"Unique suppliers: {combined['Supplier'].nunique()}")

    base_output = _month_dir(year, month)
    month_name = calendar.month_name[month]
    counts = {"BD Region": 0, "CN Region": 0}
    for supplier, group in combined.groupby("Supplier"):
        region = report_region(c for c in group["Origin Country"].unique() if pd.notna(c))
        region_dir = base_output / region
        region_dir.mkdir(exist_ok=True)

        filename = f"{safe_filename(supplier)}_{month_name}_{year}.xlsx"
        group.to_excel(region_dir / filename, index=False)
        counts[region] += 1
        print(f"Created: {region}/{filename} ({len(group)} rows)")

    print(f"\nExtraction complete! {counts['BD Region']} BD Region + "
          f"{counts['CN Region']} CN Region files in: {base_output}")
    return base_output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", choices=["monthly", "supplier"])
    args = parser.parse_args(argv)

    report_month = ask_report_month("Data Extraction Month Selection")
    extract = extract_monthly if args.kind == "monthly" else extract_by_supplier
    try:
        extract(report_month.year, report_month.month)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

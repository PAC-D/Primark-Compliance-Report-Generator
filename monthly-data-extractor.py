#!/usr/bin/env python3
"""
Monthly Data Extractor

Extracts all supplier data for a given month/year from the bi-weekly source Excel files
in the tps-pipeline data folder, and saves it to a single Excel file organized by month-year.
"""

import pandas as pd
from pathlib import Path
import sys

from supplier_data_extractor.safe_filename import safe_filename

CN_REGION_COUNTRIES = {"China", "Myanmar", "Cambodia", "Vietnam", "VietNam", "Indonesia"}

MONTH_NAMES = {1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June',
               7: 'July', 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December'}

MONTH_ABBR = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
              7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}


def _get_region_for_supplier(origin_countries) -> str:
    """Returns 'CN Region' if supplier has any CN-region country, else 'BD Region'."""
    countries = {str(c).strip() for c in origin_countries if pd.notna(c)}
    return "CN Region" if countries & CN_REGION_COUNTRIES else "BD Region"


def get_data_folder():
    """Get the source data folder path"""
    return Path(__file__).parent.parent / "tps-pipeline" / "data"


def get_files_for_month_year(year, month):
    """Find all Excel files matching the given month/year"""
    data_dir = get_data_folder()
    mon = MONTH_ABBR.get(month, '')
    pattern = f"*_{year}_{mon}_*.xlsx"
    files = list(data_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files found for {mon}/{year} in {data_dir}")
    return files


def get_month_year_input():
    """Prompt user for month and year, default to previous month"""
    from datetime import date
    today = date.today()
    if today.month == 1:
        prev_month = 12
        prev_year = today.year - 1
    else:
        prev_month = today.month - 1
        prev_year = today.year

    print(f"Enter year and month for data extraction (default: previous month {prev_month}/{prev_year})")
    year_input = input(f"Year (e.g., {prev_year}) [default: {prev_year}]: ").strip()
    month_input = input(f"Month (1-12) [default: {prev_month}]: ").strip()

    year = int(year_input) if year_input else prev_year
    month = int(month_input) if month_input else prev_month

    if not (1 <= month <= 12):
        raise ValueError("Month must be between 1 and 12")
    if year < 2000:
        raise ValueError("Year seems invalid")

    return year, month


def extract_monthly_data(year, month):
    """Extract data for all suppliers in the given month/year and save to a single Excel file,
    organized into Data_{Month}_{Year}/ folder."""
    files = get_files_for_month_year(year, month)
    print(f"Found {len(files)} file(s) for {month:02d}/{year}")

    dfs = []
    for f in files:
        df = pd.read_excel(f)
        dfs.append(df)
        print(f"Loaded: {f.name} ({len(df)} rows)")

    combined = pd.concat(dfs, ignore_index=True)
    print(f"Total combined rows: {len(combined)}")
    print(f"Unique suppliers: {combined['Supplier'].nunique()}")

    month_folder = f"Data_{MONTH_NAMES[month]}_{year}"
    output_dir = Path(__file__).parent.parent / "monthly-data-extractor" / month_folder
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_month_name = MONTH_ABBR[month] if month in MONTH_ABBR else str(month).zfill(2)
    filename = f"All_Suppliers_{safe_month_name}_{year}.xlsx"
    output_path = output_dir / filename
    combined.to_excel(output_path, index=False)

    print(f"\nExtraction complete! Single file saved to: {output_path}")


def main():
    try:
        year, month = get_month_year_input()
        print(f"\nExtracting data for {month}/{year}...")
        extract_monthly_data(year, month)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

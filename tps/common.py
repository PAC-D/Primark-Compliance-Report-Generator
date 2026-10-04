"""Helpers shared by ingest, metrics, reports, extracts and the menu."""

import calendar
from collections.abc import Iterable
from datetime import date

from tps.config import REPORT_MONTH_OFFSET

# --- Regions ------------------------------------------------------------------

CN_REGION_COUNTRIES = {"China", "Myanmar", "Cambodia", "Vietnam", "VietNam", "Indonesia"}
BD_REGION_COUNTRIES = {"Bangladesh", "India", "Pakistan", "Sri Lanka", "Morocco", "Turkey"}


def report_region(countries: Iterable[str]) -> str:
    """Output folder for a supplier: 'CN Region' if any of its origin countries
    is a CN-region country, else 'BD Region'.

    The KPI report classifies single countries the other way round (BD only if
    listed as BD) - see tps.metrics.kpi.classify_region. A country in neither
    set therefore lands in different regions; kept as-is on purpose.
    """
    names = {str(c).strip() for c in countries}
    return "CN Region" if names & CN_REGION_COUNTRIES else "BD Region"


# --- Supplier names -------------------------------------------------------------

SUPPLIER_NORMALISATION = {
    "WEIHAI BETTEX INTERNATIONAL TRADING CO., LTD": "BETTEX (HK) LIMITED (80243)",
    "YIWU HONGZHOU IMPORT & EXPORT CO LTD": "HOME JOY TEXTILE CO. LIMITED (82056)",
    "HIGH HOPE INTERNATIONAL G": "JIANGSU HUAJING INTERNATIONAL TRADE CO LTD (80070)",
    "ZHEJIANG ZHUJI IMP&EXP CO LTD": "ZHEJIANG LIJIA FOREIGN TRADE CO LTD (82990)",
    "BODYLINE (PRIVATE) LIMITED": "BODYLINE TRADING (PRIVATE) LIMITED (67247)",
    "PENTI CORAP SANAYI VE TICARET AS": "PENTI GIYIM TICARET A.S (80651)",
    "FUZHOU BICANO TRADING CO. LIMITED": "HONG KONG DIJIA TUO TECHNOLOGY CO., LIMITED (83666)",
    "TEXPORT SYNDICATE LIMITED": "TEXPORT SYNDICATE PRIVATE LIMITED (83002)",
    "JADE FOOTWEAR CO LTD": "ABUNDANT GRACE LIMITED (80064)",
    "SAIDE TEKSTIL": "SAIDE GROUP DIS TICARET AS (80111)",
    # Source files now deliver the post-rename name directly (without the ID
    # suffix) instead of the original pre-rename name above, so the old keys
    # never match. These entries key on that current spelling instead.
    "BETTEX (HK) LIMITED": "BETTEX (HK) LIMITED (80243)",
    "BODYLINE TRADING (PRIVATE) LIMITED": "BODYLINE TRADING (PRIVATE) LIMITED (67247)",
    "PENTI GIYIM TICARET A.S.": "PENTI GIYIM TICARET A.S (80651)",
    "TEXPORT SYNDICATE PRIVATE LIMITED": "TEXPORT SYNDICATE PRIVATE LIMITED (83002)",
    "SAIDE GROUP DIS TICARET AS": "SAIDE GROUP DIS TICARET AS (80111)",
}


def normalise_supplier(raw_name: str) -> str:
    stripped = raw_name.strip()
    return SUPPLIER_NORMALISATION.get(stripped, stripped)


ILLEGAL_FILENAME_CHARS = '<>:"/\\|?*'


def safe_filename(name: str) -> str:
    """Replace only the characters Windows forbids in filenames with '_'."""
    return "".join(c if c not in ILLEGAL_FILENAME_CHARS else "_" for c in str(name))


# --- Months ---------------------------------------------------------------------

def month_label(d: date) -> str:
    """Chart label, e.g. "Jun '26"."""
    return f"{calendar.month_abbr[d.month]} '{str(d.year)[-2:]}"


def add_months(d: date, months: int) -> date:
    """First day of the month `months` away from d's month."""
    year, month = divmod(d.year * 12 + d.month - 1 + months, 12)
    return date(year, month + 1, 1)


def next_month_start(d: date) -> date:
    """Exclusive upper bound for a month: handover_date < next_month_start(m)."""
    return add_months(d, 1)


def months_back(report_month: date, earliest: date, count: int = 12) -> list[date]:
    """Up to `count` month starts ending at report_month, oldest first, none
    before earliest's month. Empty when earliest is after report_month."""
    first = date(earliest.year, earliest.month, 1)
    months = (add_months(report_month, -i) for i in range(count - 1, -1, -1))
    return [m for m in months if m >= first]


def get_report_month() -> date:
    """Default report month: `report_month_offset` months before today (config)."""
    return add_months(date.today(), -REPORT_MONTH_OFFSET)


def ask_report_month(title: str) -> date:
    """Prompt for a report month; Enter or invalid input gives the default."""
    print(f"\n=== {title} ===")
    print("Enter year and month for the report (or press Enter for default: previous month)")
    year_input = input("Year (e.g., 2026) [default: previous month]: ").strip()
    month_input = input("Month (1-12) [default: previous month]: ").strip()

    if month_input:
        try:
            year = int(year_input) if year_input else date.today().year
            report_month = date(year, int(month_input), 1)
            print(f"Using specified month: {report_month.strftime('%B %Y')}")
            return report_month
        except ValueError:
            print("Invalid date. Using default.")

    print("Using default report month.")
    return get_report_month()

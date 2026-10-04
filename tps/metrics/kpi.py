"""Metrics for the monthly KPI report (all suppliers, split by region)."""

import calendar
import math
from datetime import date

from sqlalchemy import text

from tps.common import BD_REGION_COUNTRIES, add_months, month_label, months_back, next_month_start
from tps.db import get_session


def classify_region(country: str) -> str:
    """BD for a BD-region country, CN for any other (same rule as common.report_region)."""
    return "BD" if country in BD_REGION_COUNTRIES else "CN"


def get_kpi_table_months(report_month: date) -> list[date]:
    """Report month, the month before, and the same month last year."""
    return [report_month, add_months(report_month, -1), add_months(report_month, -12)]


def working_days_in_month(year: int, month: int, excluded_weekdays: tuple[int, ...]) -> int:
    _, num_days = calendar.monthrange(year, month)
    return sum(
        1 for day in range(1, num_days + 1)
        if calendar.weekday(year, month, day) not in excluded_weekdays
    )


def get_kpi_chart_months(report_month: date) -> list[date]:
    """Up to 12 months ending at report_month, none before the oldest data;
    just report_month when there is nothing to show."""
    session = get_session()
    try:
        row = session.execute(text("SELECT MIN(handover_date) AS min_date FROM raw_data")).fetchone()
    finally:
        session.close()
    if row is None or row.min_date is None:
        return [report_month]
    return months_back(report_month, row.min_date) or [report_month]


def get_kpi_monthly_tables(report_month: date) -> list[dict]:
    session = get_session()
    try:
        tables = []
        for m in get_kpi_table_months(report_month):
            end = next_month_start(m)
            rows = session.execute(text("""
                SELECT origin_country AS country,
                       COUNT(DISTINCT supplier) AS suppliers,
                       COUNT(DISTINCT factory) AS factories,
                       COUNT(*) AS reflected_lines
                FROM raw_data
                WHERE handover_date >= :start AND handover_date < :end
                GROUP BY origin_country
                ORDER BY origin_country
            """), {"start": m, "end": end}).fetchall()
            if not rows:
                continue
            table_rows = []
            totals = {"suppliers": 0, "factories": 0, "reflected_lines": 0}
            for r in rows:
                table_rows.append({
                    "country": r.country,
                    "suppliers": r.suppliers,
                    "factories": r.factories,
                    "reflected_lines": r.reflected_lines,
                })
                totals["suppliers"] += r.suppliers
                totals["factories"] += r.factories
                totals["reflected_lines"] += r.reflected_lines
            tables.append({"month_label": month_label(m), "rows": table_rows, "totals": totals})
        return tables
    finally:
        session.close()


def get_kpi_approved_by_performance(report_month: date) -> dict:
    session = get_session()
    try:
        tables = get_kpi_monthly_tables(report_month)
        present_labels = [t["month_label"] for t in tables]
        if not present_labels:
            return {"month_labels": [], "rows": []}
        counts: dict[str, dict[str, int]] = {}
        for m in get_kpi_table_months(report_month):
            label = month_label(m)
            if label not in present_labels:
                continue
            end = next_month_start(m)
            rows = session.execute(text("""
                SELECT approved_by, COUNT(*) AS lines
                FROM raw_data
                WHERE handover_date >= :start AND handover_date < :end
                  AND approved_by IS NOT NULL AND approved_by != ''
                GROUP BY approved_by
                ORDER BY approved_by
            """), {"start": m, "end": end}).fetchall()
            for r in rows:
                counts.setdefault(r.approved_by, {})[label] = r.lines
        rows_out = [
            {"approved_by": name, "lines": [c.get(label, 0) for label in present_labels]}
            for name, c in sorted(counts.items())
        ]
        return {"month_labels": present_labels, "rows": rows_out}
    finally:
        session.close()


def _count_lines(session, start: date, end: date, countries: list[str], exclude: bool = False) -> int:
    placeholders = ", ".join(f":c{i}" for i in range(len(countries)))
    op = "NOT IN" if exclude else "IN"
    params = {f"c{i}": c for i, c in enumerate(countries)}
    params.update({"start": start, "end": end})
    row = session.execute(text(f"""
        SELECT COUNT(*)
        FROM raw_data
        WHERE handover_date >= :start AND handover_date < :end
          AND origin_country {op} ({placeholders})
          AND packaging_status != 'Pending'
    """), params).fetchone()
    return int(row[0]) if row is not None and row[0] is not None else 0


def get_kpi_avg_lines_per_day(report_month: date) -> dict:
    session = get_session()
    try:
        end = next_month_start(report_month)
        bd_countries = sorted(BD_REGION_COUNTRIES)
        bd_lines = _count_lines(session, report_month, end, bd_countries, exclude=False)
        cn_lines = _count_lines(session, report_month, end, bd_countries, exclude=True)
        bd_days = working_days_in_month(report_month.year, report_month.month, (calendar.FRIDAY, calendar.SATURDAY))
        cn_days = working_days_in_month(report_month.year, report_month.month, (calendar.SATURDAY, calendar.SUNDAY))
        return {
            "bd": {
                "region": "BD",
                "lines": bd_lines,
                "working_days": bd_days,
                "avg": math.ceil(bd_lines / bd_days) if bd_days else 0,
            },
            "cn": {
                "region": "CN",
                "lines": cn_lines,
                "working_days": cn_days,
                "avg": math.ceil(cn_lines / cn_days) if cn_days else 0,
            },
        }
    finally:
        session.close()


def get_kpi_supplier_factory_trend(report_month: date) -> dict:
    session = get_session()
    try:
        months = get_kpi_chart_months(report_month)
        labels, suppliers, factories = [], [], []
        for m in months:
            end = next_month_start(m)
            row = session.execute(text("""
                SELECT COUNT(DISTINCT supplier) AS suppliers,
                       COUNT(DISTINCT factory) AS factories
                FROM raw_data
                WHERE handover_date >= :start AND handover_date < :end
            """), {"start": m, "end": end}).fetchone()
            labels.append(month_label(m))
            suppliers.append(int(row.suppliers) if row is not None and row.suppliers else 0)
            factories.append(int(row.factories) if row is not None and row.factories else 0)
        return {"labels": labels, "suppliers": suppliers, "factories": factories}
    finally:
        session.close()


def get_kpi_region_reflected_lines(report_month: date) -> dict:
    session = get_session()
    try:
        months = get_kpi_chart_months(report_month)
        labels = [month_label(m) for m in months]
        bd_counts, cn_counts = [], []
        for m in months:
            end = next_month_start(m)
            rows = session.execute(text("""
                SELECT origin_country AS country, COUNT(*) AS lines
                FROM raw_data
                WHERE handover_date >= :start AND handover_date < :end
                GROUP BY origin_country
            """), {"start": m, "end": end}).fetchall()
            bd = sum(r.lines for r in rows if classify_region(r.country) == "BD")
            cn = sum(r.lines for r in rows if classify_region(r.country) == "CN")
            bd_counts.append(bd)
            cn_counts.append(cn)
        return {"labels": labels, "bd": bd_counts, "cn": cn_counts}
    finally:
        session.close()

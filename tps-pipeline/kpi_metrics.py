import calendar
import math
from datetime import date

from sqlalchemy import text

from database import get_session
from metrics import get_last_day_of_month, get_report_month

BD_REGION_COUNTRIES = {"Bangladesh", "India", "Pakistan", "Sri Lanka", "Morocco", "Turkey"}


def classify_region(country: str) -> str:
    return "BD" if country in BD_REGION_COUNTRIES else "CN"


def month_label(d: date) -> str:
    return f"{calendar.month_abbr[d.month]} '{str(d.year)[-2:]}"


def get_kpi_table_months(report_month: date) -> list[date]:
    prev = (
        date(report_month.year, report_month.month - 1, 1)
        if report_month.month > 1
        else date(report_month.year - 1, 12, 1)
    )
    last_year = date(report_month.year - 1, report_month.month, 1)
    return [report_month, prev, last_year]


def working_days_in_month(year: int, month: int, excluded_weekdays: tuple[int, ...]) -> int:
    _, num_days = calendar.monthrange(year, month)
    return sum(
        1 for day in range(1, num_days + 1)
        if calendar.weekday(year, month, day) not in excluded_weekdays
    )


def get_kpi_chart_months(report_month: date) -> list[date]:
    session = get_session()
    try:
        row = session.execute(text("SELECT MIN(handover_date) AS min_date FROM raw_data")).fetchone()
        months = []
        cur = report_month
        while len(months) < 12:
            months.append(cur)
            cur = date(cur.year, cur.month - 1, 1) if cur.month > 1 else date(cur.year - 1, 12, 1)
        if row is None or row.min_date is None:
            return [report_month]
        db_first = date(row.min_date.year, row.min_date.month, 1)
        months = [m for m in months if m >= db_first]
        months.reverse()
        return months or [report_month]
    finally:
        session.close()


def get_kpi_monthly_tables(report_month: date) -> list[dict]:
    session = get_session()
    try:
        tables = []
        for m in get_kpi_table_months(report_month):
            end = get_last_day_of_month(m)
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
            end = get_last_day_of_month(m)
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
        end = get_last_day_of_month(report_month)
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
            end = get_last_day_of_month(m)
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
            end = get_last_day_of_month(m)
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

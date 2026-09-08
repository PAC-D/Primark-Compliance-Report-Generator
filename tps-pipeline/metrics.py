from datetime import date

from sqlalchemy import text, func
from sqlalchemy.orm import Session

from database import get_session
import yaml
from pathlib import Path


CONFIG_PATH = Path(__file__).parent / "config.yaml"

with open(CONFIG_PATH) as f:
    _config = yaml.safe_load(f)

_report_month_offset = _config.get("app", {}).get("report_month_offset", 1)


def get_report_month(year: int | None = None, month: int | None = None) -> date:
    if year is not None and month is not None:
        return date(year, month, 1)
    today = date.today()
    month = today.month - _report_month_offset
    year = today.year
    if month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def get_last_day_of_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _get_chart_month_range(supplier: str, report_month: date) -> list[date]:
    """Returns list of month start dates from (report_month - 11) to report_month, but no earlier than supplier's oldest data. Always 12 months or fewer."""
    min_date, _ = get_supplier_data_range(supplier)
    db_first = date(min_date.year, min_date.month, 1)
    first_adj = report_month.month - 11
    first_year = report_month.year
    while first_adj <= 0:
        first_adj += 12
        first_year -= 1
    actual_first = date(first_year, first_adj, 1)
    if db_first > actual_first:
        actual_first = db_first
    months = []
    cur = date(report_month.year, report_month.month, 1)
    while cur >= actual_first and len(months) < 12:
        months.append(cur)
        if cur.month == 1:
            cur = date(cur.year - 1, 12, 1)
        else:
            cur = date(cur.year, cur.month - 1, 1)
    months.reverse()
    return months


def get_supplier_data_range(supplier: str) -> tuple[date, date]:
    """Returns (oldest_date, newest_date) of handover data for a supplier. Falls back to report_month if no data."""
    session = get_session()
    try:
        row = session.execute(text("""
            SELECT MIN(handover_date) as min_date, MAX(handover_date) as max_date
            FROM raw_data
            WHERE supplier = :supplier
        """), {"supplier": supplier}).fetchone()
        if row is None or row.min_date is None or row.max_date is None:
            default = get_report_month()
            return (default, default)
        return (row.min_date, row.max_date)
    finally:
        session.close()


def get_compliance_rate(supplier: str, year: int, month: int) -> float:
    session = get_session()
    try:
        start = date(year, month, 1)
        end = get_last_day_of_month(start)
        query = text("""
            SELECT
                COUNT(*) FILTER (WHERE compliance_status = 'Compliant') AS compliant,
                COUNT(*) AS total
            FROM raw_data
            WHERE supplier = :supplier
              AND handover_date >= :start
              AND handover_date < :end
        """)
        row = session.execute(query, {"supplier": supplier, "start": start, "end": end}).fetchone()
        if row is None or row.total == 0:
            return 0.0
        return round(row.compliant / row.total * 100, 2)
    finally:
        session.close()


def get_monthly_compliance_scores(supplier: str, report_month: date | None = None) -> tuple[list[float], list[str]]:
    """Returns (scores, labels) for chart. Always shows 12 months ending at report_month (0 for empty months)."""
    if report_month is None:
        report_month = get_report_month()

    session = get_session()
    try:
        months_list = _get_chart_month_range(supplier, report_month)

        if not months_list:
            return ([0.0], ["No Data"])

        import calendar
        scores = []
        labels = []
        for month_start in months_list:
            month_end = get_last_day_of_month(month_start)
            row = session.execute(text("""
                SELECT
                    COUNT(*) FILTER (WHERE compliance_status = 'Compliant') AS compliant,
                    COUNT(*) AS total
                FROM raw_data
                WHERE supplier = :supplier AND handover_date >= :start AND handover_date < :end
            """), {"supplier": supplier, "start": month_start, "end": month_end}).fetchone()
            if row.total == 0:
                score = 0.0
            else:
                score = round(row.compliant / row.total * 100, 1)
            scores.append(score)
            labels.append(f"{calendar.month_abbr[month_start.month]} '{str(month_start.year)[-2:]}")

        return (scores, labels)
    finally:
        session.close()


def get_standard_carton_scores(supplier: str, report_month: date | None = None) -> tuple[list[float], list[str]]:
    """Returns (scores, labels). Always shows 12 months ending at report_month (0 for empty months)."""
    if report_month is None:
        report_month = get_report_month()

    session = get_session()
    try:
        months_list = _get_chart_month_range(supplier, report_month)

        if not months_list:
            return ([0.0], ["No Data"])

        import calendar
        scores = []
        labels = []
        for month_start in months_list:
            month_end = get_last_day_of_month(month_start)
            row = session.execute(text("""
                SELECT
                    COUNT(*) FILTER (WHERE packaging_status = 'Approved') AS standard,
                    COUNT(*) AS total
                FROM raw_data
                WHERE supplier = :supplier AND handover_date >= :start AND handover_date < :end
            """), {"supplier": supplier, "start": month_start, "end": month_end}).fetchone()
            score = round(row.standard / row.total * 100, 1) if row.total > 0 else 0.0
            scores.append(score)
            labels.append(f"{calendar.month_abbr[month_start.month]} '{str(month_start.year)[-2:]}")

        return (scores, labels)
    finally:
        session.close()


def get_density_scores(supplier: str, report_month: date | None = None) -> tuple[list[float], list[str]]:
    """Returns (scores, labels). Always shows 12 months ending at report_month (0 for empty months)."""
    if report_month is None:
        report_month = get_report_month()

    session = get_session()
    try:
        months_list = _get_chart_month_range(supplier, report_month)

        if not months_list:
            return ([0.0], ["No Data"])

        import calendar
        scores = []
        labels = []
        for month_start in months_list:
            month_end = get_last_day_of_month(month_start)
            row = session.execute(text("""
                SELECT AVG(density) FROM raw_data
                WHERE supplier = :supplier AND handover_date >= :start AND handover_date < :end
                  AND packaging_status = 'Approved' AND density IS NOT NULL
            """), {"supplier": supplier, "start": month_start, "end": month_end}).fetchone()
            score = round(float(row[0]), 1) if row[0] is not None else 0.0
            scores.append(score)
            labels.append(f"{calendar.month_abbr[month_start.month]} '{str(month_start.year)[-2:]}")

        return (scores, labels)
    finally:
        session.close()


def get_volume_scores(supplier: str, report_month: date | None = None) -> tuple[list[int], list[str]]:
    """Returns (scores, labels). Always shows 12 months ending at report_month (0 for empty months)."""
    if report_month is None:
        report_month = get_report_month()

    session = get_session()
    try:
        months_list = _get_chart_month_range(supplier, report_month)

        if not months_list:
            return ([0], ["No Data"])

        import calendar
        scores = []
        labels = []
        for month_start in months_list:
            month_end = get_last_day_of_month(month_start)
            row = session.execute(text("""
                SELECT COALESCE(SUM(po_qty), 0) FROM raw_data
                WHERE supplier = :supplier AND handover_date >= :start AND handover_date < :end
            """), {"supplier": supplier, "start": month_start, "end": month_end}).fetchone()
            score = int(row[0]) if row[0] is not None else 0
            scores.append(score)
            labels.append(f"{calendar.month_abbr[month_start.month]} '{str(month_start.year)[-2:]}")

        return (scores, labels)
    finally:
        session.close()


def get_local_rankings(supplier: str, report_month: date | None = None) -> list[dict]:
    if report_month is None:
        report_month = get_report_month()
    session = get_session()
    try:
        end = get_last_day_of_month(report_month)

        origin_query = text("""
            SELECT DISTINCT origin_country
            FROM raw_data
            WHERE supplier = :supplier
              AND handover_date >= :start AND handover_date < :end
            ORDER BY origin_country
        """)
        origin_rows = session.execute(origin_query, {"supplier": supplier, "start": report_month, "end": end}).fetchall()
        countries = [row.origin_country for row in origin_rows]

        results = []
        for country in countries:
            rate_query = text("""
                WITH rates AS (
                    SELECT
                        supplier,
                        COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) AS rate
                    FROM raw_data
                    WHERE handover_date >= :start AND handover_date < :end
                      AND origin_country = :country
                    GROUP BY supplier
                ),
                ranked AS (
                    SELECT supplier, rate, DENSE_RANK() OVER (ORDER BY rate DESC) AS dr
                    FROM rates
                )
                SELECT dr FROM ranked WHERE supplier = :supplier
            """)
            rank_row = session.execute(rate_query, {
                "start": report_month, "end": end,
                "country": country, "supplier": supplier
            }).fetchone()

            total_query = text("""
                SELECT COUNT(DISTINCT supplier) AS total
                FROM raw_data
                WHERE handover_date >= :start AND handover_date < :end
                  AND origin_country = :country
            """)
            total_row = session.execute(total_query, {
                "start": report_month, "end": end, "country": country
            }).fetchone()

            supplier_rate_query = text("""
                SELECT COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) AS rate
                FROM raw_data
                WHERE supplier = :supplier
                  AND handover_date >= :start AND handover_date < :end
                  AND origin_country = :country
                GROUP BY supplier
            """)
            supplier_rate_row = session.execute(supplier_rate_query, {
                "start": report_month, "end": end,
                "country": country, "supplier": supplier
            }).fetchone()

            same_rate_query = text("""
                SELECT COUNT(*) AS cnt
                FROM (
                    SELECT COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) AS rate
                    FROM raw_data
                    WHERE handover_date >= :start AND handover_date < :end
                      AND origin_country = :country
                    GROUP BY supplier
                    HAVING COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) = :rate
                ) t
            """)
            same_rate_count = session.execute(same_rate_query, {
                "start": report_month, "end": end,
                "country": country, "rate": supplier_rate_row.rate if supplier_rate_row else None
            }).fetchone()

            rank = rank_row.dr if rank_row else 0
            total = total_row.total if total_row else 0
            shared = same_rate_count is not None and same_rate_count.cnt > 1

            results.append({
                "country": country,
                "rank": rank,
                "total": total,
                "shared": shared
            })

        return results
    finally:
        session.close()


def get_global_ranking(supplier: str, report_month: date | None = None) -> tuple[int, int, bool]:
    session = get_session()
    try:
        if report_month is None:
            report_month = get_report_month()
        end = get_last_day_of_month(report_month)
        query = text("""
            WITH rates AS (
                SELECT
                    supplier,
                    COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) AS rate
                FROM raw_data
                WHERE handover_date >= :start AND handover_date < :end
                GROUP BY supplier
            ),
            ranked AS (
                SELECT supplier, rate, DENSE_RANK() OVER (ORDER BY rate DESC) AS dr
                FROM rates
            )
            SELECT dr FROM ranked WHERE supplier = :supplier
        """)
        rank_row = session.execute(query, {"start": report_month, "end": end, "supplier": supplier}).fetchone()

        count_query = text("""
            SELECT COUNT(DISTINCT supplier) AS total
            FROM raw_data
            WHERE handover_date >= :start AND handover_date < :end
        """)
        total_row = session.execute(count_query, {"start": report_month, "end": end}).fetchone()

        if rank_row is None or total_row is None:
            return (0, 0, False)

        rank = rank_row.dr
        total = total_row.total

        rate_query = text("""
            SELECT COUNT(*) AS cnt
            FROM (
                SELECT COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) AS rate
                FROM raw_data
                WHERE handover_date >= :start AND handover_date < :end
                GROUP BY supplier
                HAVING COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) = (
                    SELECT COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0)
                    FROM raw_data
                    WHERE supplier = :supplier
                      AND handover_date >= :start AND handover_date < :end
                    GROUP BY supplier
                )
            ) t
        """)
        same_rate_count = session.execute(rate_query, {"start": report_month, "end": end, "supplier": supplier}).fetchone()
        shared = same_rate_count is not None and same_rate_count.cnt > 1

        return (rank, total, shared)
    finally:
        session.close()


def get_supplier_kpis(supplier: str, report_month: date | None = None) -> dict:
    session = get_session()
    try:
        if report_month is None:
            report_month = get_report_month()
        end = get_last_day_of_month(report_month)
        query = text("""
            SELECT
                string_agg(DISTINCT origin_country, ', ' ORDER BY origin_country) AS origin_countries,
                COUNT(DISTINCT factory) AS factory_count,
                COUNT(*) AS total_lines,
                COUNT(*) FILTER (WHERE compliance_status = 'Compliant') AS compliant_count,
                COUNT(*) FILTER (WHERE compliance_status = 'Non-compliant') AS non_compliant_count
            FROM raw_data
            WHERE supplier = :supplier
              AND handover_date >= :start
              AND handover_date < :end
        """)
        row = session.execute(query, {"supplier": supplier, "start": report_month, "end": end}).fetchone()
        if row is None:
            return {
                "origin_country": None,
                "factory_count": 0,
                "total_lines": 0,
                "compliant_count": 0,
                "non_compliant_count": 0
            }
        return {
            "origin_country": row.origin_countries,
            "factory_count": row.factory_count,
            "total_lines": row.total_lines,
            "compliant_count": row.compliant_count,
            "non_compliant_count": row.non_compliant_count
        }
    finally:
        session.close()


def get_associated_factories(supplier: str, report_month: date | None = None) -> list[dict]:
    """Returns list of factories with data in report_month, with compliance rate per factory."""
    if report_month is None:
        report_month = get_report_month()
    session = get_session()
    try:
        end = get_last_day_of_month(report_month)
        query = text("""
            SELECT
                factory,
                string_agg(DISTINCT origin_country, ', ' ORDER BY origin_country) AS origin_countries,
                COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) * 100 AS compliance_rate
            FROM raw_data
            WHERE supplier = :supplier
              AND handover_date >= :start AND handover_date < :end
            GROUP BY factory
            ORDER BY factory
        """)
        rows = session.execute(query, {"supplier": supplier, "start": report_month, "end": end}).fetchall()
        return [
            {
                "factory": row.factory,
                "origin_countries": row.origin_countries,
                "compliance_rate": round(row.compliance_rate, 1) if row.compliance_rate is not None else 0.0,
            }
            for row in rows
        ]
    finally:
        session.close()


def get_line_details(supplier: str, report_month: date | None = None) -> tuple[list[dict], dict]:
    """Returns (list of factory rows with count/confirmation data, totals dict) for report month."""
    if report_month is None:
        report_month = get_report_month()
    session = get_session()
    try:
        end = get_last_day_of_month(report_month)
        query = text("""
            SELECT
                factory,
                COUNT(DISTINCT destination_po) AS dest_po_count,
                COUNT(*) AS reflected_lines,
                COUNT(*) FILTER (WHERE packaging_status = 'Pending') AS pending,
                COUNT(*) FILTER (WHERE packaging_status = 'Approved') AS approved,
                COUNT(*) FILTER (WHERE packaging_status = 'Approval Rejected') AS rejected,
                COUNT(*) FILTER (WHERE packaging_status = 'Escalated') AS escalated
            FROM raw_data
            WHERE supplier = :supplier
              AND handover_date >= :start AND handover_date < :end
            GROUP BY factory
            ORDER BY factory
        """)
        rows = session.execute(query, {"supplier": supplier, "start": report_month, "end": end}).fetchall()
        factories = []
        totals = {"dest_po_count": 0, "reflected_lines": 0, "pending": 0, "approved": 0, "rejected": 0, "escalated": 0}
        for row in rows:
            factories.append({
                "factory": row.factory,
                "dest_po_count": row.dest_po_count,
                "reflected_lines": row.reflected_lines,
                "pending": row.pending,
                "approved": row.approved,
                "rejected": row.rejected,
                "escalated": row.escalated,
            })
            totals["dest_po_count"] += row.dest_po_count
            totals["reflected_lines"] += row.reflected_lines
            totals["pending"] += row.pending
            totals["approved"] += row.approved
            totals["rejected"] += row.rejected
            totals["escalated"] += row.escalated
        return factories, totals
    finally:
        session.close()


def get_compliance_data(supplier: str, report_month: date | None = None) -> list[dict]:
    """Returns factory-level compliance data (standard carton %, total carton qty, corrugated sqm) for compliant rows only in report month."""
    if report_month is None:
        report_month = get_report_month()
    session = get_session()
    try:
        end = get_last_day_of_month(report_month)
        query = text("""
            SELECT
                factory,
                COUNT(*) FILTER (WHERE packaging_status = 'Approved')::FLOAT / NULLIF(COUNT(*), 0) * 100 AS standard_carton_pct,
                COALESCE(SUM(po_qty) FILTER (WHERE packaging_status = 'Approved'), 0) AS total_carton_qty,
                COALESCE(SUM(
                    po_qty * ((carton_length_mm / 10.0 + 6.0) * (carton_width_mm / 10.0 + carton_height_mm / 10.0 + 4.0) * 2)
                ) FILTER (WHERE packaging_status = 'Approved' AND carton_length_mm IS NOT NULL AND carton_width_mm IS NOT NULL AND carton_height_mm IS NOT NULL), 0) / 10000.0 AS corrugated_sqm
            FROM raw_data
            WHERE supplier = :supplier
              AND handover_date >= :start AND handover_date < :end
            GROUP BY factory
            ORDER BY factory
        """)
        rows = session.execute(query, {"supplier": supplier, "start": report_month, "end": end}).fetchall()
        return [
            {
                "factory": row.factory,
                "standard_carton_pct": round(row.standard_carton_pct, 1) if row.standard_carton_pct is not None else 0.0,
                "total_carton_qty": int(row.total_carton_qty or 0),
                "corrugated_sqm": round(row.corrugated_sqm, 1) if row.corrugated_sqm is not None else 0.0,
            }
            for row in rows
        ]
    finally:
        session.close()
    session = get_session()
    try:
        query = text("""
            SELECT
                factory,
                string_agg(DISTINCT origin_country, ', ' ORDER BY origin_country) AS origin_countries,
                COUNT(*) AS total_lines,
                COUNT(*) FILTER (WHERE compliance_status = 'Compliant') AS compliant_lines,
                COUNT(DISTINCT destination_po) AS dest_po_count,
                COUNT(*) FILTER (WHERE packaging_status = 'Pending') AS pending,
                COUNT(*) FILTER (WHERE packaging_status = 'Approved') AS approved,
                COUNT(*) FILTER (WHERE packaging_status = 'Approval Rejected') AS rejected,
                COUNT(*) FILTER (WHERE packaging_status = 'Escalated') AS escalated,
                COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) AS compliance_rate,
                COUNT(*) FILTER (WHERE packaging_status = 'Approved')::FLOAT / NULLIF(COUNT(*), 0) * 100 AS standard_carton_pct,
                COALESCE(SUM(po_qty) FILTER (WHERE packaging_status = 'Approved'), 0) AS total_carton_qty,
                AVG(units_per_carton) FILTER (WHERE packaging_status = 'Approved') AS avg_units_per_carton,
                AVG(density) FILTER (WHERE packaging_status = 'Approved' AND density IS NOT NULL) AS avg_density,
                AVG(carton_length_mm) FILTER (WHERE packaging_status = 'Approved' AND carton_length_mm IS NOT NULL) AS avg_carton_length_mm,
                AVG(carton_width_mm) FILTER (WHERE packaging_status = 'Approved' AND carton_width_mm IS NOT NULL) AS avg_carton_width_mm,
                AVG(carton_height_mm) FILTER (WHERE packaging_status = 'Approved' AND carton_height_mm IS NOT NULL) AS avg_carton_height_mm
            FROM raw_data
            WHERE supplier = :supplier
            GROUP BY factory
            ORDER BY factory
        """)
        rows = session.execute(query, {"supplier": supplier}).fetchall()
        result = []
        for row in rows:
            result.append({
                "factory": row.factory,
                "origin_countries": row.origin_countries,
                "total_lines": row.total_lines,
                "compliant_lines": row.compliant_lines,
                "dest_po_count": row.dest_po_count,
                "pending": row.pending,
                "approved": row.approved,
                "rejected": row.rejected,
                "escalated": row.escalated,
                "compliance_rate": round(row.compliance_rate, 1) if row.compliance_rate is not None else 0.0,
                "standard_carton_pct": round(row.standard_carton_pct, 1) if row.standard_carton_pct is not None else 0.0,
                "total_carton_qty": row.total_carton_qty or 0,
                "avg_units_per_carton": row.avg_units_per_carton,
                "avg_density": round(row.avg_density, 1) if row.avg_density is not None else None,
                "avg_carton_length_mm": row.avg_carton_length_mm,
                "avg_carton_width_mm": row.avg_carton_width_mm,
                "avg_carton_height_mm": row.avg_carton_height_mm
            })
        return result
    finally:
        session.close()


def get_transactions(supplier: str, report_month: date | None = None) -> list[dict]:
    session = get_session()
    try:
        if report_month is None:
            report_month = get_report_month()
        end = get_last_day_of_month(report_month)
        query = text("""
            SELECT
                area, sub_area, origin_country, origin_port,
                supplier, factory, destination_po, kimball,
                colour_code, description, size,
                po_qty, handover_date,
                carton_matrix_code,
                units_per_carton,
                carton_length_mm, carton_width_mm, carton_height_mm,
                packaging_supplier,
                updated_date, updated_by, approved_date, approved_by,
                packaging_status,
                source_file,
                carton_type, cbm, density, compliance_status
            FROM raw_data
            WHERE supplier = :supplier
              AND handover_date >= :start
              AND handover_date < :end
            ORDER BY handover_date, updated_date
        """)
        rows = session.execute(query, {"supplier": supplier, "start": report_month, "end": end}).fetchall()
        return [dict(row._mapping) for row in rows]
    finally:
        session.close()


def _get_chart_month_range_for_all(report_month: date) -> list[date]:
    """Returns list of month start dates from (report_month - 11) to report_month across all suppliers."""
    session = get_session()
    try:
        row = session.execute(text("""
            SELECT MIN(handover_date) as min_date FROM raw_data
        """)).fetchone()
        if row is None or row.min_date is None:
            return [date(report_month.year, report_month.month, 1)]
        db_first = date(row.min_date.year, row.min_date.month, 1)
        first_adj = report_month.month - 11
        first_year = report_month.year
        while first_adj <= 0:
            first_adj += 12
            first_year -= 1
        actual_first = date(first_year, first_adj, 1)
        if db_first > actual_first:
            actual_first = db_first
        months = []
        cur = date(report_month.year, report_month.month, 1)
        while cur >= actual_first and len(months) < 12:
            months.append(cur)
            if cur.month == 1:
                cur = date(cur.year - 1, 12, 1)
            else:
                cur = date(cur.year, cur.month - 1, 1)
        months.reverse()
        return months
    finally:
        session.close()


def get_summary_sources(report_month: date) -> dict:
    """Returns total suppliers and factories for the report month."""
    session = get_session()
    try:
        end = get_last_day_of_month(report_month)
        query = text("""
            SELECT
                COUNT(DISTINCT supplier) AS total_suppliers,
                COUNT(DISTINCT factory) AS total_factories
            FROM raw_data
            WHERE handover_date >= :start AND handover_date < :end
        """)
        row = session.execute(query, {"start": report_month, "end": end}).fetchone()
        return {
            "total_suppliers": row.total_suppliers if row and row.total_suppliers else 0,
            "total_factories": row.total_factories if row and row.total_factories else 0
        }
    finally:
        session.close()


def get_summary_country_compliance(report_month: date) -> list[dict]:
    """Returns compliance rates by country, sorted by country name."""
    session = get_session()
    try:
        end = get_last_day_of_month(report_month)
        query = text("""
            SELECT
                origin_country AS country,
                COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) * 100 AS compliance_rate
            FROM raw_data
            WHERE handover_date >= :start AND handover_date < :end
            GROUP BY origin_country
            ORDER BY origin_country
        """)
        rows = session.execute(query, {"start": report_month, "end": end}).fetchall()
        return [
            {"country": row.country, "compliance_rate": round(row.compliance_rate, 2) if row.compliance_rate else 0.0}
            for row in rows
        ]
    finally:
        session.close()


def get_summary_country_volume(report_month: date) -> list[dict]:
    """Returns volume data by country: carton_qty, product_qty, unit_cbm (compliant rows only)."""
    session = get_session()
    try:
        end = get_last_day_of_month(report_month)

        qry = text("""
            SELECT
                origin_country AS country,
                COALESCE(SUM(po_qty) FILTER (WHERE compliance_status = 'Compliant'), 0)::INT AS carton_qty,
                COALESCE(SUM(po_qty * units_per_carton) FILTER (WHERE compliance_status = 'Compliant'), 0)::INT AS product_qty
            FROM raw_data
            WHERE handover_date >= :start AND handover_date < :end
            GROUP BY origin_country
            ORDER BY origin_country
        """)
        rows = session.execute(qry, {"start": report_month, "end": end}).fetchall()

        result = []
        for row in rows:
            country = row.country
            carton_qty = row.carton_qty if row.carton_qty else 0
            product_qty = row.product_qty if row.product_qty else 0

            if True:
                density_row = session.execute(text("""
                    SELECT AVG(density)::FLOAT AS avg_density
                    FROM raw_data
                    WHERE origin_country = :country
                      AND compliance_status = 'Compliant'
                      AND handover_date >= :start AND handover_date < :end
                      AND density IS NOT NULL
                """), {"country": country, "start": report_month, "end": end}).fetchone()
                unit_cbm = int(round(float(density_row.avg_density))) if density_row and density_row.avg_density else 0

            result.append({
                "country": country,
                "carton_qty": carton_qty,
                "product_qty": product_qty,
                "unit_cbm": unit_cbm
            })

        return result
    finally:
        session.close()


def get_summary_country_monthly_trend(report_month: date) -> tuple[dict, list[str], list[str]]:
    """Returns (country_data, labels, country_order) for 12-month compliance trend by country."""
    session = get_session()
    try:
        months_list = _get_chart_month_range_for_all(report_month)

        if not months_list:
            return ({"No Data": [0.0]}, ["No Data"], ["No Data"])

        import calendar
        country_data = {}
        country_order = []

        for month_start in months_list:
            month_end = get_last_day_of_month(month_start)
            rows = session.execute(text("""
                SELECT
                    origin_country AS country,
                    COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) * 100 AS rate
                FROM raw_data
                WHERE handover_date >= :start AND handover_date < :end
                GROUP BY origin_country
            """), {"start": month_start, "end": month_end}).fetchall()

            month_rates = {row.country: round(row.rate, 2) if row.rate else 0.0 for row in rows}

            for country in month_rates:
                if country not in country_order:
                    country_order.append(country)
                if country not in country_data:
                    country_data[country] = []
                country_data[country].append(month_rates[country])

        all_countries = set(country_data.keys())
        for country in all_countries:
            while len(country_data[country]) < len(months_list):
                country_data[country].insert(0, 0.0)

        labels = [
            f"{calendar.month_abbr[m.month]} '{str(m.year)[-2:]}"
            for m in months_list
        ]

        return (country_data, labels, country_order)
    finally:
        session.close()


def get_summary_line_details(report_month: date) -> tuple[list[dict], dict]:
    """Returns (list of country rows with count/confirmation data, totals dict) for report month."""
    session = get_session()
    try:
        end = get_last_day_of_month(report_month)
        query = text("""
            SELECT
                origin_country,
                COUNT(DISTINCT destination_po) AS dest_po_count,
                COUNT(*) AS reflected_lines,
                COUNT(*) FILTER (WHERE packaging_status = 'Pending') AS pending,
                COUNT(*) FILTER (WHERE packaging_status = 'Approved') AS approved,
                COUNT(*) FILTER (WHERE packaging_status = 'Approval Rejected') AS rejected,
                COUNT(*) FILTER (WHERE packaging_status = 'Escalated') AS escalated
            FROM raw_data
            WHERE handover_date >= :start AND handover_date < :end
            GROUP BY origin_country
            ORDER BY origin_country
        """)
        rows = session.execute(query, {"start": report_month, "end": end}).fetchall()
        details = []
        totals = {"dest_po_count": 0, "reflected_lines": 0, "pending": 0, "approved": 0, "rejected": 0, "escalated": 0}
        for row in rows:
            details.append({
                "country": row.origin_country,
                "dest_po_count": row.dest_po_count,
                "reflected_lines": row.reflected_lines,
                "pending": row.pending,
                "approved": row.approved,
                "rejected": row.rejected,
                "escalated": row.escalated,
            })
            totals["dest_po_count"] += row.dest_po_count
            totals["reflected_lines"] += row.reflected_lines
            totals["pending"] += row.pending
            totals["approved"] += row.approved
            totals["rejected"] += row.rejected
            totals["escalated"] += row.escalated
        return details, totals
    finally:
        session.close()


def get_top_suppliers(report_month: date) -> list[dict]:
    """Returns top performing suppliers (compliance_rate >= 95%) for report month."""
    session = get_session()
    try:
        end = get_last_day_of_month(report_month)
        query = text("""
            SELECT
                supplier,
                string_agg(DISTINCT origin_country, ', ' ORDER BY origin_country) AS origin_countries,
                COUNT(DISTINCT factory) AS factory_count,
                COUNT(DISTINCT destination_po) AS dest_po_count,
                COUNT(*) AS reflected_lines,
                COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) * 100 AS compliance_rate
            FROM raw_data
            WHERE handover_date >= :start AND handover_date < :end
            GROUP BY supplier
            HAVING COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) * 100 >= 95
            ORDER BY compliance_rate DESC, reflected_lines DESC
        """)
        rows = session.execute(query, {"start": report_month, "end": end}).fetchall()
        results = []
        for idx, row in enumerate(rows, start=1):
            results.append({
                "sl": idx,
                "supplier": row.supplier,
                "origin_countries": row.origin_countries,
                "factory_count": row.factory_count,
                "dest_po_count": row.dest_po_count,
                "reflected_lines": row.reflected_lines,
                "compliance_rate": round(row.compliance_rate, 1),
            })
        return results
    finally:
        session.close()

def get_suppliers_below_threshold(report_month: date, threshold: float = 40.0) -> list[dict]:
    """Returns suppliers where report_month compliance < threshold AND 3-month avg < threshold."""
    import calendar
    session = get_session()
    try:
        months_to_check = []
        cur = report_month
        for _ in range(3):
            months_to_check.append(cur)
            year = cur.year
            month = cur.month - 1
            if month < 1:
                month = 12
                year -= 1
            cur = date(year, month, 1)

        month_ranges = []
        for m in months_to_check:
            end = get_last_day_of_month(m)
            month_ranges.append((m, end))

        query = text("""
            WITH monthly_rates AS (
                SELECT
                    supplier,
                    :m0 AS month_start,
                    string_agg(DISTINCT origin_country, ', ' ORDER BY origin_country) AS origin_countries,
                    COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) * 100 AS rate,
                    COUNT(DISTINCT factory) AS factory_count,
                    COUNT(DISTINCT destination_po) AS dest_po_count,
                    COUNT(*) AS reflected_lines,
                    SUM(po_qty) AS qty
                FROM raw_data
                WHERE handover_date >= :m0_start AND handover_date < :m0_end
                GROUP BY supplier

                UNION ALL

                SELECT
                    supplier,
                    :m1 AS month_start,
                    NULL AS origin_countries,
                    COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) * 100 AS rate,
                    NULL::BIGINT AS factory_count,
                    NULL::BIGINT AS dest_po_count,
                    NULL::BIGINT AS reflected_lines,
                    NULL::BIGINT AS qty
                FROM raw_data
                WHERE handover_date >= :m1_start AND handover_date < :m1_end
                GROUP BY supplier

                UNION ALL

                SELECT
                    supplier,
                    :m2 AS month_start,
                    NULL AS origin_countries,
                    COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) * 100 AS rate,
                    NULL::BIGINT AS factory_count,
                    NULL::BIGINT AS dest_po_count,
                    NULL::BIGINT AS reflected_lines,
                    NULL::BIGINT AS qty
                FROM raw_data
                WHERE handover_date >= :m2_start AND handover_date < :m2_end
                GROUP BY supplier
            )
            SELECT
                r0.supplier,
                r0.origin_countries,
                r0.factory_count,
                r0.dest_po_count,
                r0.qty,
                r0.reflected_lines,
                r0.rate AS compliance_rate,
                COALESCE(r1.rate, 0) AS prev_1_rate,
                COALESCE(r2.rate, 0) AS prev_2_rate,
                (COALESCE(r0.rate, 0) + COALESCE(r1.rate, 0) + COALESCE(r2.rate, 0))
                  / NULLIF(
                      (CASE WHEN r0.rate IS NOT NULL THEN 1 ELSE 0 END)
                    + (CASE WHEN r1.rate IS NOT NULL THEN 1 ELSE 0 END)
                    + (CASE WHEN r2.rate IS NOT NULL THEN 1 ELSE 0 END),
                    0
                  ) AS avg_3month
            FROM (SELECT supplier, origin_countries, factory_count, dest_po_count, qty, reflected_lines, rate FROM monthly_rates WHERE month_start = :m0) r0
            LEFT JOIN (SELECT supplier, rate FROM monthly_rates WHERE month_start = :m1) r1 ON r0.supplier = r1.supplier
            LEFT JOIN (SELECT supplier, rate FROM monthly_rates WHERE month_start = :m2) r2 ON r0.supplier = r2.supplier
            WHERE
                  (COALESCE(r0.rate, 0) + COALESCE(r1.rate, 0) + COALESCE(r2.rate, 0))
                    / NULLIF(
                        (CASE WHEN r0.rate IS NOT NULL THEN 1 ELSE 0 END)
                      + (CASE WHEN r1.rate IS NOT NULL THEN 1 ELSE 0 END)
                      + (CASE WHEN r2.rate IS NOT NULL THEN 1 ELSE 0 END),
                      0
                    ) < :threshold
              AND r0.rate < :threshold
            ORDER BY avg_3month ASC, r0.rate ASC
        """)
        m0, m0_end = month_ranges[0]
        m1, m1_end = month_ranges[1]
        m2, m2_end = month_ranges[2]
        rows = session.execute(query, {
            "m0": m0, "m0_start": m0, "m0_end": m0_end,
            "m1": m1, "m1_start": m1, "m1_end": m1_end,
            "m2": m2, "m2_start": m2, "m2_end": m2_end,
            "threshold": threshold
        }).fetchall()
        results = []
        for idx, row in enumerate(rows, start=1):
            results.append({
                "sl": idx,
                "supplier": row.supplier,
                "origin_country": row.origin_countries,
                "factory_count": row.factory_count,
                "dest_po_count": row.dest_po_count,
                "qty": row.qty,
                "reflected_lines": row.reflected_lines,
                "compliance_rate": round(row.compliance_rate, 1),
                "prev_1_rate": round(row.prev_1_rate, 1),
                "prev_2_rate": round(row.prev_2_rate, 1),
                "avg_3month": round(row.avg_3month, 1),
            })
        return results
    finally:
        session.close()


def get_supplier_emails_map() -> dict[str, str]:
    """Returns dict mapping lowercase supplier name to comma-separated emails."""
    session = get_session()
    try:
        rows = session.execute(text("""
            SELECT supplier_name, email FROM supplier_emails ORDER BY supplier_name, email
        """)).fetchall()

        email_map: dict[str, list[str]] = {}
        for row in rows:
            key = row.supplier_name
            if key not in email_map:
                email_map[key] = []
            email_map[key].append(row.email)

        return {k: ", ".join(v) for k, v in email_map.items()}
    finally:
        session.close()


def get_all_suppliers_24month_trend(report_month: date) -> tuple[list[dict], list[str]]:
    """Returns (supplier_trends, month_labels) for available months up to 24 from report month."""
    session = get_session()
    try:
        # Get actual month range from database (same as chart trend uses)
        months_list = _get_chart_month_range_for_all(report_month)

        if not months_list:
            return ([], [])

        # Limit to last 24 months if more available
        months_list = months_list[-24:] if len(months_list) > 24 else months_list

        import calendar
        month_labels = [f"{calendar.month_abbr[m.month]} '{str(m.year)[-2:]}" for m in months_list]

        supplier_data = {}
        for month_start in months_list:
            month_end = get_last_day_of_month(month_start)
            rows = session.execute(text("""
                SELECT supplier,
                    COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) * 100 AS rate
                FROM raw_data WHERE handover_date >= :start AND handover_date < :end
                GROUP BY supplier
            """), {"start": month_start, "end": month_end}).fetchall()
            for row in rows:
                if row.supplier not in supplier_data:
                    supplier_data[row.supplier] = {"rates": {}}
                supplier_data[row.supplier]["rates"][month_start] = round(row.rate, 1) if row.rate is not None else None

        results = []
        for supplier, data in sorted(supplier_data.items()):
            rates = []
            for m in months_list:
                rates.append(data["rates"].get(m))
            results.append({
                "supplier": supplier,
                "rates": rates,
            })
        return (results, month_labels)
    finally:
        session.close()

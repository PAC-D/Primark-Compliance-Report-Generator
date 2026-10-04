"""Per-supplier metrics for the compliance report (one supplier, one month)."""

from datetime import date

from sqlalchemy import text

from tps.common import get_report_month, month_label, months_back, next_month_start
from tps.db import get_session


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
        end = next_month_start(start)
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


def _chart_months(supplier: str, report_month: date) -> list[date]:
    """Up to 12 months ending at report_month, none before the supplier's oldest data."""
    min_date, _ = get_supplier_data_range(supplier)
    return months_back(report_month, min_date)


def _monthly_series(supplier: str, report_month: date | None, sql: str, score) -> tuple[list, list[str]]:
    """(values, labels) for a 12-month chart. `sql` gets :supplier/:start/:end
    and returns one row; score(row) turns that row into the month's value."""
    if report_month is None:
        report_month = get_report_month()

    session = get_session()
    try:
        months = _chart_months(supplier, report_month)
        if not months:
            return ([0.0], ["No Data"])

        scores = []
        for month_start in months:
            row = session.execute(text(sql), {
                "supplier": supplier, "start": month_start, "end": next_month_start(month_start),
            }).fetchone()
            scores.append(score(row))
        return (scores, [month_label(m) for m in months])
    finally:
        session.close()


def get_monthly_compliance_scores(supplier: str, report_month: date | None = None) -> tuple[list[float], list[str]]:
    return _monthly_series(supplier, report_month, """
        SELECT
            COUNT(*) FILTER (WHERE compliance_status = 'Compliant') AS compliant,
            COUNT(*) AS total
        FROM raw_data
        WHERE supplier = :supplier AND handover_date >= :start AND handover_date < :end
    """, lambda row: 0.0 if row.total == 0 else round(row.compliant / row.total * 100, 1))


def get_standard_carton_scores(supplier: str, report_month: date | None = None) -> tuple[list[float], list[str]]:
    return _monthly_series(supplier, report_month, """
        SELECT
            COUNT(*) FILTER (WHERE packaging_status = 'Approved') AS standard,
            COUNT(*) AS total
        FROM raw_data
        WHERE supplier = :supplier AND handover_date >= :start AND handover_date < :end
    """, lambda row: round(row.standard / row.total * 100, 1) if row.total > 0 else 0.0)


def get_density_scores(supplier: str, report_month: date | None = None) -> tuple[list[float], list[str]]:
    return _monthly_series(supplier, report_month, """
        SELECT AVG(density) FROM raw_data
        WHERE supplier = :supplier AND handover_date >= :start AND handover_date < :end
          AND packaging_status = 'Approved' AND density IS NOT NULL
    """, lambda row: round(float(row[0]), 1) if row[0] is not None else 0.0)


def get_local_rankings(supplier: str, report_month: date | None = None) -> list[dict]:
    if report_month is None:
        report_month = get_report_month()
    session = get_session()
    try:
        end = next_month_start(report_month)

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
        end = next_month_start(report_month)
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
        end = next_month_start(report_month)
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
        end = next_month_start(report_month)
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
        end = next_month_start(report_month)
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
        end = next_month_start(report_month)
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


def get_transactions(supplier: str, report_month: date | None = None) -> list[dict]:
    session = get_session()
    try:
        if report_month is None:
            report_month = get_report_month()
        end = next_month_start(report_month)
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


def get_suppliers_for_month(report_month: date) -> list[str]:
    """Every supplier with handover data in the month."""
    session = get_session()
    try:
        result = session.execute(
            text("SELECT DISTINCT supplier FROM raw_data WHERE EXTRACT(YEAR FROM handover_date) = :year AND EXTRACT(MONTH FROM handover_date) = :month"),
            {"year": report_month.year, "month": report_month.month}
        )
        return [row[0] for row in result]
    finally:
        session.close()

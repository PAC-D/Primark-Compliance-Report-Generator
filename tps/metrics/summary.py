"""All-supplier metrics for the monthly summary workbook."""

from datetime import date

from sqlalchemy import text

from tps.common import add_months, month_label, months_back, next_month_start
from tps.db import get_session


def _chart_months(report_month: date) -> list[date]:
    """Up to 12 months ending at report_month, none before the oldest data.
    Just report_month when raw_data is empty."""
    session = get_session()
    try:
        row = session.execute(text("SELECT MIN(handover_date) AS min_date FROM raw_data")).fetchone()
    finally:
        session.close()
    if row is None or row.min_date is None:
        return [report_month]
    return months_back(report_month, row.min_date)


def get_latest_data_month() -> date | None:
    """First day of the newest month with handover data; None when empty."""
    session = get_session()
    try:
        latest = session.execute(text("SELECT MAX(handover_date) FROM raw_data")).scalar()
    finally:
        session.close()
    return date(latest.year, latest.month, 1) if latest else None


def get_summary_sources(report_month: date) -> dict:
    """Returns total suppliers and factories for the report month."""
    session = get_session()
    try:
        end = next_month_start(report_month)
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
        end = next_month_start(report_month)
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


def get_summary_country_monthly_trend(report_month: date) -> tuple[dict, list[str], list[str]]:
    """Returns (country_data, labels, country_order) for the 12-month compliance
    trend by country. A month in which a country shipped nothing is None (a
    blank cell), never 0%."""
    session = get_session()
    try:
        months_list = _chart_months(report_month)

        if not months_list:
            return ({"No Data": [0.0]}, ["No Data"], ["No Data"])

        # Insertion order = order countries first appear, which is country_order.
        rates_by_country: dict[str, dict[date, float]] = {}
        for month_start in months_list:
            month_end = next_month_start(month_start)
            rows = session.execute(text("""
                SELECT
                    origin_country AS country,
                    COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) * 100 AS rate
                FROM raw_data
                WHERE handover_date >= :start AND handover_date < :end
                GROUP BY origin_country
            """), {"start": month_start, "end": month_end}).fetchall()
            for row in rows:
                rates_by_country.setdefault(row.country, {})[month_start] = (
                    round(row.rate, 2) if row.rate else 0.0)

        country_data = {country: [rates.get(m) for m in months_list]
                        for country, rates in rates_by_country.items()}
        return (country_data, [month_label(m) for m in months_list], list(rates_by_country))
    finally:
        session.close()


def get_summary_line_details(report_month: date) -> tuple[list[dict], dict]:
    """Returns (list of country rows with count/confirmation data, totals dict) for report month."""
    session = get_session()
    try:
        end = next_month_start(report_month)
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
        end = next_month_start(report_month)
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
    session = get_session()
    try:
        month_ranges = [(m, next_month_start(m))
                        for m in (add_months(report_month, -i) for i in range(3))]

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
            email_map.setdefault(row.supplier_name, []).append(row.email)

        return {k: ", ".join(v) for k, v in email_map.items()}
    finally:
        session.close()


def get_all_suppliers_trend(report_month: date) -> tuple[list[dict], list[str]]:
    """Returns (supplier_trends, month_labels): every supplier's compliance rate
    for each chart month (None where it had no lines)."""
    session = get_session()
    try:
        months_list = _chart_months(report_month)

        if not months_list:
            return ([], [])

        month_labels = [month_label(m) for m in months_list]

        rates_by_supplier: dict[str, dict[date, float | None]] = {}
        for month_start in months_list:
            month_end = next_month_start(month_start)
            rows = session.execute(text("""
                SELECT supplier,
                    COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) * 100 AS rate
                FROM raw_data WHERE handover_date >= :start AND handover_date < :end
                GROUP BY supplier
            """), {"start": month_start, "end": month_end}).fetchall()
            for row in rows:
                rates_by_supplier.setdefault(row.supplier, {})[month_start] = (
                    round(row.rate, 1) if row.rate is not None else None)

        results = [
            {"supplier": supplier, "rates": [rates.get(m) for m in months_list]}
            for supplier, rates in sorted(rates_by_supplier.items())
        ]
        return (results, month_labels)
    finally:
        session.close()

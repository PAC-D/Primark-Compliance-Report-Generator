"""Metrics for the hosted compliance dashboard. Rates use the reports' rule
(Compliant lines / all lines) and the reports' region, ranking and threshold
rules, so dashboard numbers equal the reports'."""

from dataclasses import dataclass
import math
from datetime import date

from sqlalchemy import text

from tps.common import add_months, like_contains, month_label, months_back, next_month_start, report_region
from tps.db import get_session
from tps.metrics.kpi import classify_region, get_kpi_table_months, region_working_days
from tps.reports.kpi_report import pct_change
from tps.reports.supplier_report import rate_band

TOP_RATE = 95.0
FOLLOW_UP_RATE = 40.0


@dataclass(frozen=True)
class Filters:
    month: date  # first of the month
    region: str | None = None  # "BD" | "CN"
    country: str | None = None
    supplier: str | None = None  # part-text, case-insensitive
    factory: str | None = None  # part-text, case-insensitive
    approved_by: str | None = None  # KPI only


def line_filter_sql(f: Filters, start: date, end: date) -> tuple[str, dict]:
    """WHERE conditions for the lines in [start, end) matching the filters.
    Region is not here: callers apply it after aggregating. Values are bound."""
    parts, params = ["handover_date >= :start AND handover_date < :end"], {"start": start, "end": end}
    if f.country:
        parts.append("origin_country = :country")
        params["country"] = f.country
    if f.supplier:
        parts.append("supplier ILIKE :supplier")
        params["supplier"] = like_contains(f.supplier)
    if f.factory:
        parts.append("factory ILIKE :factory")
        params["factory"] = like_contains(f.factory)
    if f.approved_by:
        parts.append("approved_by = :approved_by")
        params["approved_by"] = f.approved_by
    return " AND ".join(parts), params


def _pct(compliant: int, total: int) -> float | None:
    return compliant / total * 100 if total else None


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def _supplier_rows(session, f: Filters, month: date) -> dict[str, dict]:
    """Supplier -> its month's counts, for lines matching the filters (not region)."""
    where, params = line_filter_sql(f, month, next_month_start(month))
    rows = session.execute(text(f"""
        SELECT supplier,
               array_agg(DISTINCT origin_country) AS countries,
               COUNT(DISTINCT factory) AS factories,
               COUNT(*) AS lines,
               COUNT(*) FILTER (WHERE compliance_status = 'Compliant') AS compliant,
               COUNT(*) FILTER (WHERE packaging_status = 'Approved') AS approved,
               COUNT(*) FILTER (WHERE packaging_status = 'Pending') AS pending,
               COUNT(*) FILTER (WHERE packaging_status = 'Approval Rejected') AS rejected,
               COUNT(*) FILTER (WHERE packaging_status = 'Escalated') AS escalated
        FROM raw_data WHERE {where}
        GROUP BY supplier
    """), params).fetchall()
    out = {}
    for r in rows:
        countries = sorted(c for c in (r.countries or []) if c)
        out[r.supplier] = {
            "name": r.supplier, "countries": countries,
            "factories": r.factories, "lines": r.lines, "compliant": r.compliant,
            "rate": _pct(r.compliant, r.lines),
            "status": {"approved": r.approved, "pending": r.pending,
                       "rejected": r.rejected, "escalated": r.escalated},
        }
    return out


def _regions(session, month: date) -> dict[str, str]:
    """Supplier -> 'BD'/'CN' from ALL its origin countries in the month, as its
    report does; the Country/Factory/Supplier filters never change it."""
    rows = session.execute(text("""
        SELECT supplier, array_agg(DISTINCT origin_country) AS all_countries
        FROM raw_data
        WHERE handover_date >= :start AND handover_date < :end
        GROUP BY supplier
    """), {"start": month, "end": next_month_start(month)}).fetchall()
    return {r.supplier: report_region([c for c in (r.all_countries or []) if c])[:2] for r in rows}


def _global_ranks(session, month: date) -> dict[str, int]:
    """Supplier -> dense rank by unrounded rate over every supplier in the month
    (the same ranking as supplier.get_global_ranking); no filters apply."""
    rows = session.execute(text("""
        WITH rates AS (
            SELECT supplier,
                   COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) AS rate
            FROM raw_data
            WHERE handover_date >= :start AND handover_date < :end
            GROUP BY supplier
        )
        SELECT supplier, DENSE_RANK() OVER (ORDER BY rate DESC) AS dr FROM rates
    """), {"start": month, "end": next_month_start(month)}).fetchall()
    return {r.supplier: r.dr for r in rows}


def _trend(session, f: Filters) -> dict:
    """Up to 12 months of rates: BD and CN by country region, all together.
    Honours the line filters; a month with no lines is None."""
    first = session.execute(text("SELECT MIN(handover_date) AS min_date FROM raw_data")).fetchone()
    months = months_back(f.month, first.min_date) if first and first.min_date else [f.month]
    if not months:
        return {"labels": [], "bd": [], "cn": [], "all": []}
    where, params = line_filter_sql(f, months[0], next_month_start(f.month))
    rows = session.execute(text(f"""
        SELECT date_trunc('month', handover_date)::date AS month, origin_country AS country,
               COUNT(*) FILTER (WHERE compliance_status = 'Compliant') AS compliant,
               COUNT(*) AS total
        FROM raw_data WHERE {where}
        GROUP BY month, origin_country
    """), params).fetchall()
    sums = {key: {m: [0, 0] for m in months} for key in ("bd", "cn", "all")}
    for r in rows:
        for key in (classify_region(r.country).lower(), "all"):
            if r.month in sums[key]:
                sums[key][r.month][0] += r.compliant
                sums[key][r.month][1] += r.total
    return {"labels": [month_label(m) for m in months],
            **{key: [_round(_pct(*sums[key][m])) for m in months] for key in sums}}


def _countries(session, f: Filters) -> list[dict]:
    where, params = line_filter_sql(f, f.month, next_month_start(f.month))
    rows = session.execute(text(f"""
        SELECT origin_country AS country,
               COUNT(*) FILTER (WHERE compliance_status = 'Compliant') AS compliant,
               COUNT(*) AS total
        FROM raw_data WHERE {where}
        GROUP BY origin_country
    """), params).fetchall()
    rates = [(r.country, _pct(r.compliant, r.total)) for r in rows
             if r.country and (not f.region or classify_region(r.country) == f.region)]
    rates.sort(key=lambda x: (-x[1], x[0]))
    return [{"country": c, "rate": _round(rate)} for c, rate in rates]


def _overall(rows: dict[str, dict]) -> float | None:
    return _pct(sum(r["compliant"] for r in rows.values()), sum(r["lines"] for r in rows.values()))


def _top(rows: dict[str, dict]) -> int:
    return sum(r["rate"] >= TOP_RATE for r in rows.values())


def supplier_compliance(f: Filters) -> dict:
    session = get_session()
    try:
        cur, prev, prev2 = (_supplier_rows(session, f, add_months(f.month, -i)) for i in range(3))
        ranks = _global_ranks(session, f.month)
        regions = _regions(session, f.month)
        trend = _trend(session, f)
        countries = _countries(session, f)
    finally:
        session.close()

    # Region is decided once, from the report month; earlier months follow by name.
    if f.region:
        cur = {n: r for n, r in cur.items() if regions.get(n) == f.region}
        prev = {n: r for n, r in prev.items() if n in cur}
        prev2 = {n: r for n, r in prev2.items() if n in cur}

    suppliers, follow_up = [], 0
    for name, r in cur.items():
        rates = [x[name]["rate"] for x in (cur, prev, prev2) if name in x]
        avg = sum(rates) / len(rates)
        if r["rate"] < FOLLOW_UP_RATE and avg < FOLLOW_UP_RATE:
            follow_up += 1
        suppliers.append({
            "name": name, "region": regions[name], "countries": r["countries"],
            "factories": r["factories"], "lines": r["lines"],
            "compliance": _round(r["rate"]), "band": rate_band(r["rate"]), "avg_3m": _round(avg),
            "change": _round(r["rate"] - prev[name]["rate"]) if name in prev else None,
            "rank": ranks.get(name),
        })
    suppliers.sort(key=lambda s: (s["compliance"], s["name"]))

    bands = [rate_band(r["rate"]) for r in cur.values()]
    status = {k: sum(r["status"][k] for r in cur.values()) for k in ("approved", "pending", "rejected", "escalated")}
    lines = sum(r["lines"] for r in cur.values())
    compliance, prev_compliance = _overall(cur), _overall(prev)
    return {
        "month": f.month.strftime("%Y-%m"),
        "totals": {"suppliers": len(cur), "lines": lines},
        "cards": {
            "compliance": _round(compliance),
            "compliance_change": None if compliance is None or prev_compliance is None
            else _round(compliance - prev_compliance),
            "top_count": _top(cur),
            "top_change": _top(cur) - _top(prev) if prev else None,
            "follow_up_count": follow_up,
            "status": {**status, "total": lines},
        },
        "bands": {"all": len(bands), **{b: bands.count(b) for b in ("high", "mid", "low")}},
        "trend": trend,
        "countries": countries,
        "suppliers": suppliers,
    }


def filter_options(month: date) -> dict:
    """The month's distinct origin countries and approvers, sorted: the filter lists."""
    session = get_session()
    params = {"start": month, "end": next_month_start(month)}
    try:
        values = {col: session.execute(text(f"""
            SELECT DISTINCT {col} AS value FROM raw_data
            WHERE handover_date >= :start AND handover_date < :end AND {col} IS NOT NULL AND {col} != ''
        """), params).fetchall() for col in ("origin_country", "approved_by")}  # fixed names, not input
    finally:
        session.close()
    return {"countries": sorted(r.value for r in values["origin_country"]),
            "approvers": sorted(r.value for r in values["approved_by"])}


def search(month: date, q: str) -> dict:
    """Suppliers and factories with lines in the month whose name contains q (max 20 each)."""
    q = q.strip()
    if not q:
        return {"suppliers": [], "factories": []}
    params = {"start": month, "end": next_month_start(month), "q": like_contains(q)}
    session = get_session()
    try:
        suppliers = session.execute(text("""
            SELECT DISTINCT supplier FROM raw_data
            WHERE handover_date >= :start AND handover_date < :end AND supplier ILIKE :q
            ORDER BY supplier LIMIT 20
        """), params).fetchall()
        pairs = session.execute(text("""
            SELECT DISTINCT factory, supplier FROM raw_data
            WHERE handover_date >= :start AND handover_date < :end AND factory ILIKE :q AND supplier IS NOT NULL
            ORDER BY factory, supplier
        """), params).fetchall()
    finally:
        session.close()
    factories: dict[str, list[str]] = {}
    for r in pairs:
        factories.setdefault(r.factory, []).append(r.supplier)
    return {"suppliers": [r.supplier for r in suppliers],
            "factories": [{"factory": f, "suppliers": s} for f, s in list(factories.items())[:20]]}


def _kpi_rows(session, f: Filters, start: date) -> list:
    """Per month/country/supplier/factory line counts from `start` to the end of
    the report month, for lines matching the filters (region applied by caller)."""
    where, params = line_filter_sql(f, start, next_month_start(f.month))
    rows = session.execute(text(f"""
        SELECT date_trunc('month', handover_date)::date AS month, origin_country AS country,
               supplier, factory, COUNT(*) AS lines,
               COUNT(*) FILTER (WHERE packaging_status != 'Pending') AS active
        FROM raw_data WHERE {where}
        GROUP BY month, origin_country, supplier, factory
    """), params).fetchall()
    return [r for r in rows if not f.region or classify_region(r.country) == f.region]


def _kpi_approvers(session, f: Filters, start: date, now: date, prev: date) -> list[dict]:
    where, params = line_filter_sql(f, start, next_month_start(f.month))
    rows = session.execute(text(f"""
        SELECT date_trunc('month', handover_date)::date AS month, approved_by,
               origin_country AS country, COUNT(*) AS lines
        FROM raw_data
        WHERE {where} AND approved_by IS NOT NULL AND approved_by != ''
        GROUP BY month, approved_by, origin_country
    """), params).fetchall()
    counts: dict[str, list[int]] = {}
    for r in rows:
        if r.month in (now, prev) and (not f.region or classify_region(r.country) == f.region):
            counts.setdefault(r.approved_by, [0, 0])[r.month != now] += r.lines
    return [{"name": n, "lines": c, "change_pct": pct_change(c[0], c[1])} for n, c in sorted(counts.items())]


def kpi(f: Filters) -> dict:
    table_months = get_kpi_table_months(f.month)
    session = get_session()
    try:
        first = session.execute(text("SELECT MIN(handover_date) AS min_date FROM raw_data")).fetchone()
        chart = (months_back(f.month, first.min_date) if first and first.min_date else []) or [f.month]
        start = min(chart[0], table_months[-1])
        rows = _kpi_rows(session, f, start)
        approvers = _kpi_approvers(session, f, start, f.month, table_months[1])
    finally:
        session.close()

    # Per chart month: reflected lines and distinct suppliers/factories, as the KPI report counts them.
    seen = {m: {"bd": [0, set(), set()], "cn": [0, set(), set()]} for m in chart}
    by_country: dict[str, dict[date, int]] = {}
    active = {"bd": 0, "cn": 0}
    for r in rows:
        region = classify_region(r.country).lower()
        if r.month in seen:
            cell = seen[r.month][region]
            cell[0] += r.lines
            if r.supplier is not None:
                cell[1].add(r.supplier)
            if r.factory is not None:
                cell[2].add(r.factory)
        if r.country:
            by_country.setdefault(r.country, {}).setdefault(r.month, 0)
            by_country[r.country][r.month] += r.lines
        if r.month == f.month:
            active[region] += r.active

    def total(m, i):  # a supplier/factory in both regions counts once overall
        return len(seen[m]["bd"][i] | seen[m]["cn"][i]) if i else seen[m]["bd"][0] + seen[m]["cn"][0]

    now, before = f.month, chart[-2] if len(chart) > 1 else None

    def card(i):
        return total(now, i), (total(before, i) if before else None)

    def diff(now_, before_):
        return None if before_ is None else now_ - before_

    days = region_working_days(f.month)
    lines_now, lines_prev = card(0)
    suppliers_now, suppliers_prev = card(1)
    factories_now, factories_prev = card(2)

    countries = []
    for country in sorted(by_country):
        cells = [by_country[country].get(m) for m in table_months]
        countries.append({"country": country, "region": classify_region(country),
                          "cells": cells,
                          "share": round((cells[0] or 0) / lines_now * 100) if lines_now else 0})

    return {
        "month": f.month.strftime("%Y-%m"),
        "cards": {
            "lines": lines_now, "lines_change_pct": pct_change(lines_now, lines_prev),
            "suppliers": suppliers_now, "suppliers_change": diff(suppliers_now, suppliers_prev),
            "factories": factories_now, "factories_change": diff(factories_now, factories_prev),
            **{k: {"lines": active[k], "working_days": days[k],
                   "avg": math.ceil(active[k] / days[k]) if days[k] else 0} for k in ("bd", "cn")},
        },
        "region_lines": {"labels": [month_label(m) for m in chart],
                         **{k: [seen[m][k][0] for m in chart] for k in ("bd", "cn")}},
        "people": {"labels": [month_label(m) for m in chart],
                   **{k: {"suppliers": [len(seen[m][k][1]) for m in chart],
                          "factories": [len(seen[m][k][2]) for m in chart]} for k in ("bd", "cn")}},
        "table_months": [month_label(m) for m in table_months],
        "countries": countries,
        "approvers": approvers,
    }

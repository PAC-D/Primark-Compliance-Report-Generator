"""Integration tests run against a scratch PostgreSQL named by TPS_TEST_DATABASE_URL.
init_db() drops raw_data, so production-looking databases are refused."""

import os
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

import tps.db

# (supplier, factory, country, lines, compliant lines) per month
SPEC = [
    ("S_BD", "F1", "Bangladesh", 6, 3),
    ("S_BD", "F2", "India", 4, 2),
    ("S_CN", "F3", "China", 8, 4),
    ("S_MIX", "F4", "Bangladesh", 3, 1),
    ("S_MIX", "F5", "China", 3, 1),
    ("S_TOP", "F6", "China", 10, 10),
    ("S_LOW", "F7", "Vietnam", 5, 1),
]


def _rows(month: date):
    n = 0
    for supplier, factory, country, lines, ok in SPEC:
        for i in range(lines):
            n += 1
            yield {
                "supplier": supplier, "factory": factory, "country": country,
                "handover": month.replace(day=1 + i % 25),
                "compliance": "Compliant" if i < ok else "Non-Compliant",
                # one Pending line per month; one line updated after month end
                "status": "Pending" if n == 1 else "Approved",
                "approver": None if n == 1 else ("alice" if n % 2 else "bob"),
                "updated": datetime(month.year, month.month, 1, tzinfo=timezone.utc)
                if n != 2 else datetime(month.year + (month.month == 12), month.month % 12 + 1, 5, tzinfo=timezone.utc),
            }


@pytest.fixture(autouse=True)
def test_db():
    url = os.environ.get("TPS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("set TPS_TEST_DATABASE_URL to a scratch PostgreSQL to run integration tests")
    parsed = make_url(url)
    if (parsed.host or "").endswith("rds.amazonaws.com") or parsed.database == "tps_compliance":
        pytest.skip("refusing: TPS_TEST_DATABASE_URL points at a real database (init_db drops raw_data)")

    engine = create_engine(url)
    previous, tps.db._engine = tps.db._engine, engine
    try:
        tps.db.init_db()
        with engine.begin() as conn:
            for month in MONTHS:
                for r in _rows(month):
                    conn.execute(text("""
                        INSERT INTO raw_data (supplier, factory, origin_country, handover_date, compliance_status,
                                              packaging_status, approved_by, updated_date, destination_po)
                        VALUES (:supplier, :factory, :country, :handover, :compliance, :status, :approver, :updated, 'PO1')
                    """), r)
        yield engine
    finally:
        tps.db._engine = previous
        engine.dispose()


MONTHS = [date(2026, 4, 1), date(2026, 5, 1)]

# KPI Report + Clear Database Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Clear Database" menu option (delete rows, keep tables) and a single-PDF "Transit Packaging System (TPS) KPI Report" with monthly country tables, approved-by performance, avg lines/day by region, and 12-month charts.

**Architecture:** Three new files — `kpi_metrics.py` (all SQL/data queries), `kpi_renderer.py` (Jinja2 rendering), `templates/kpi_report.html.j2` — plus additive edits to `database.py` (two clear functions) and `menu.py` (two new menu options/handlers). PDF via existing `pdfgen.html_to_pdf`.

**Tech Stack:** Python 3.14, SQLAlchemy (text SQL), PostgreSQL, Jinja2, Chart.js (CDN), Playwright (PDF), pytest (mocked sessions).

## Global Constraints

- **DO NOT modify existing behavior or existing code** except the exact additive edits listed in Tasks 2 and 10 (`database.py` append functions; `menu.py` import line, banner, two new handlers, two new `main()` branches). Do NOT touch `renderer.py`, `summary_renderer.py`, `summary_excel_renderer.py`, `metrics.py`, `processor.py`, `pdfgen.py`, existing templates, or existing handlers.
- Report month **M** = user-selected month, default previous month (same prompt pattern as `handle_generate_summary_report`).
- BD region = exactly `{"Bangladesh", "India", "Pakistan", "Sri Lanka", "Morocco", "Turkey"}` (full names verified in live DB). CN region = **all other countries** (NOT IN BD set).
- Avg lines/day: numerator = lines where `packaging_status != 'Pending'`. BD working days = days excluding Friday+Saturday; CN working days = days excluding Saturday+Sunday.
- Monthly tables: skip any of the 3 months (M, M-1, M-last-year) with no data.
- Output: `output/KPI_Report_<Month_Year>.pdf` (via `config["paths"]["output_dir"]`).
- Tests: `pytest`, mock `kpi_metrics.get_session` / `database._engine` — never require a live DB.
- Country names in DB: Bangladesh, India, Pakistan, Sri Lanka, Morocco, Turkey, China, Cambodia, Vietnam.

---

### Task 1: Working Windows test environment

**Files:**
- Create: `.venv-win/` (venv at repo root `D:\Primark Report Generator`)
- Test: none (baseline check)

**Interfaces:**
- Consumes: nothing
- Produces: `.venv-win\Scripts\python.exe` with all deps; proof existing tests pass

The project `.venv` is a Linux/WSL venv and cannot run on Windows. The Windows machine has no usable Python packages. Create a fresh venv so all later tasks can run tests.

- [ ] **Step 1: Create the venv**

```powershell
& "C:\Users\Shoaib\AppData\Local\Python\bin\python.exe" -m venv "D:\Primark Report Generator\.venv-win"
```

- [ ] **Step 2: Install dependencies**

```powershell
& "D:\Primark Report Generator\.venv-win\Scripts\python.exe" -m pip install sqlalchemy pyyaml pytest pandas openpyxl jinja2 pypdf playwright
```

- [ ] **Step 3: Run existing tests to confirm green baseline**

```powershell
& "D:\Primark Report Generator\.venv-win\Scripts\python.exe" -m pytest "D:\Primark Report Generator\tps-pipeline\tests" -v
```

Expected: all existing tests pass. (If `test_processor.py` / `test_renderer.py` fail due to missing module paths, run from the `tps-pipeline` directory instead: set workdir to `D:\Primark Report Generator\tps-pipeline` and run `..\..\.venv-win\Scripts\python.exe -m pytest tests -v`.)

- [ ] **Step 4: Commit**

```bash
git add .venv-win 2>/dev/null; git add -f .venv-win/.gitignore 2>/dev/null
git commit -m "chore: add Windows venv for local development"
```

(If git identity is missing, ask the user how to proceed — do not set git config without permission.)

---

### Task 2: Clear-database functions in `database.py`

**Files:**
- Modify: `tps-pipeline/database.py` (append two functions after `clear_supplier_emails`, around line 102)
- Test: `tps-pipeline/tests/test_database_clear.py` (create)

**Interfaces:**
- Consumes: existing `_engine`, `text` from sqlalchemy
- Produces: `clear_raw_data() -> None`, `clear_all_tables() -> None` (used by menu Task 10)

- [ ] **Step 1: Write the failing test**

`tps-pipeline/tests/test_database_clear.py`:

```python
import sys
sys.path.insert(0, "..")

import pytest
from unittest.mock import patch, MagicMock

import database


@pytest.fixture
def mock_conn():
    mock_engine = MagicMock()
    conn = mock_engine.connect.return_value.__enter__.return_value
    with patch("database._engine", mock_engine):
        yield conn


def _statements(conn):
    return [str(c.args[0]) for c in conn.execute.call_args_list]


def test_clear_raw_data_deletes_rows_only(mock_conn):
    database.clear_raw_data()
    stmts = _statements(mock_conn)
    assert any("DELETE FROM raw_data" in s for s in stmts)
    assert not any("DROP TABLE" in s.upper() for s in stmts)
    mock_conn.commit.assert_called_once()


def test_clear_all_tables_deletes_both_tables(mock_conn):
    database.clear_all_tables()
    stmts = _statements(mock_conn)
    assert any("DELETE FROM raw_data" in s for s in stmts)
    assert any("DELETE FROM supplier_emails" in s for s in stmts)
    assert not any("DROP TABLE" in s.upper() for s in stmts)
    mock_conn.commit.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
& "D:\Primark Report Generator\.venv-win\Scripts\python.exe" -m pytest "D:\Primark Report Generator\tps-pipeline\tests\test_database_clear.py" -v
```

Expected: FAIL with ImportError (`clear_raw_data` not defined).

- [ ] **Step 3: Implement**

Append to `tps-pipeline/database.py` after the existing `clear_supplier_emails` function:

```python
def clear_raw_data() -> None:
    """Clears all rows from the raw_data table (keeps the table)."""
    with _engine.connect() as conn:
        conn.execute(text("DELETE FROM raw_data"))
        conn.commit()


def clear_all_tables() -> None:
    """Clears all rows from all data tables (keeps the tables)."""
    with _engine.connect() as conn:
        conn.execute(text("DELETE FROM raw_data"))
        conn.execute(text("DELETE FROM supplier_emails"))
        conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Same command as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tps-pipeline/database.py tps-pipeline/tests/test_database_clear.py
git commit -m "feat: add clear_raw_data and clear_all_tables"
```

---

### Task 3: `kpi_metrics.py` — constants, helpers, chart months

**Files:**
- Create: `tps-pipeline/kpi_metrics.py` (helpers section)
- Test: `tps-pipeline/tests/test_kpi_metrics.py` (create, helpers only)

**Interfaces:**
- Consumes: `database.get_session`, `metrics.get_last_day_of_month`, `metrics.get_report_month`
- Produces:
  - `BD_REGION_COUNTRIES: set[str]`
  - `classify_region(country: str) -> str` → `"BD"` or `"CN"`
  - `month_label(d: date) -> str` → e.g. `"Jun '26"`
  - `get_kpi_table_months(report_month: date) -> list[date]` → `[M, M-1, M-last-year]`
  - `working_days_in_month(year: int, month: int, excluded_weekdays: tuple[int, ...]) -> int`
  - `get_kpi_chart_months(report_month: date) -> list[date]` → up to 12 months ending at M, clamped to earliest data month (fallback `[M]`)

- [ ] **Step 1: Write the failing tests**

`tps-pipeline/tests/test_kpi_metrics.py` (append to this file in Tasks 4-7):

```python
import sys
sys.path.insert(0, "..")

import calendar
from datetime import date
from unittest.mock import patch, MagicMock

import pytest

import kpi_metrics


class TestHelpers:
    def test_classify_region_bd(self):
        for c in ("Bangladesh", "India", "Pakistan", "Sri Lanka", "Morocco", "Turkey"):
            assert kpi_metrics.classify_region(c) == "BD"

    def test_classify_region_cn(self):
        assert kpi_metrics.classify_region("China") == "CN"
        assert kpi_metrics.classify_region("Cambodia") == "CN"
        assert kpi_metrics.classify_region("Unknown") == "CN"

    def test_month_label(self):
        assert kpi_metrics.month_label(date(2026, 6, 1)) == "Jun '26"
        assert kpi_metrics.month_label(date(2025, 12, 1)) == "Dec '25"

    def test_table_months_order(self):
        months = kpi_metrics.get_kpi_table_months(date(2026, 6, 1))
        assert months == [date(2026, 6, 1), date(2026, 5, 1), date(2025, 6, 1)]

    def test_table_months_january_rollover(self):
        months = kpi_metrics.get_kpi_table_months(date(2026, 1, 1))
        assert months == [date(2026, 1, 1), date(2025, 12, 1), date(2025, 1, 1)]

    def test_working_days_bd_excludes_fri_sat(self):
        assert kpi_metrics.working_days_in_month(2026, 3, (calendar.FRIDAY, calendar.SATURDAY)) == 23

    def test_working_days_cn_excludes_sat_sun(self):
        assert kpi_metrics.working_days_in_month(2026, 3, (calendar.SATURDAY, calendar.SUNDAY)) == 22

    def test_chart_months_no_data_falls_back(self):
        with patch("kpi_metrics.get_session") as mock_session:
            mock_session.return_value.execute.return_value.fetchone.return_value = None
            months = kpi_metrics.get_kpi_chart_months(date(2026, 6, 1))
            assert months == [date(2026, 6, 1)]

    def test_chart_months_full_12(self):
        with patch("kpi_metrics.get_session") as mock_session:
            row = MagicMock()
            row.min_date = date(2025, 1, 1)
            mock_session.return_value.execute.return_value.fetchone.return_value = row
            months = kpi_metrics.get_kpi_chart_months(date(2026, 6, 1))
            assert len(months) == 12
            assert months[0] == date(2025, 7, 1)
            assert months[-1] == date(2026, 6, 1)
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
& "D:\Primark Report Generator\.venv-win\Scripts\python.exe" -m pytest "D:\Primark Report Generator\tps-pipeline\tests\test_kpi_metrics.py" -v
```

Expected: FAIL with ImportError (`kpi_metrics` module not found).

- [ ] **Step 3: Implement**

`tps-pipeline/kpi_metrics.py`:

```python
import calendar
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
        if row is not None and row.min_date is not None:
            db_first = date(row.min_date.year, row.min_date.month, 1)
            months = [m for m in months if m >= db_first]
        months.reverse()
        return months or [report_month]
    finally:
        session.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Same command as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tps-pipeline/kpi_metrics.py tps-pipeline/tests/test_kpi_metrics.py
git commit -m "feat: add kpi_metrics helpers"
```

---

### Task 4: `get_kpi_monthly_tables`

**Files:**
- Modify: `tps-pipeline/kpi_metrics.py` (append)
- Test: `tps-pipeline/tests/test_kpi_metrics.py` (append class `TestMonthlyTables`)

**Interfaces:**
- Consumes: Task 3 helpers
- Produces: `get_kpi_monthly_tables(report_month: date) -> list[dict]` — each dict: `{"month_label": str, "rows": [{"country": str, "suppliers": int, "factories": int, "reflected_lines": int}], "totals": {"suppliers": int, "factories": int, "reflected_lines": int}}`; months with zero rows omitted; empty list if no data at all

- [ ] **Step 1: Write the failing tests**

```python
class TestMonthlyTables:
    def test_three_months_with_data(self):
        with patch("kpi_metrics.get_session") as mock_session:
            inst = mock_session.return_value
            def fake_row(country, s, f, r):
                row = MagicMock()
                row.country, row.suppliers, row.factories, row.reflected_lines = country, s, f, r
                return row
            inst.execute.return_value.fetchall.side_effect = [
                [fake_row("Bangladesh", 2, 3, 10)],
                [fake_row("China", 1, 1, 5)],
                [fake_row("India", 1, 2, 4)],
            ]
            tables = kpi_metrics.get_kpi_monthly_tables(date(2026, 6, 1))
            assert [t["month_label"] for t in tables] == ["Jun '26", "May '26", "Jun '25"]
            assert tables[0]["rows"][0]["country"] == "Bangladesh"
            assert tables[0]["totals"] == {"suppliers": 2, "factories": 3, "reflected_lines": 10}

    def test_skips_empty_months(self):
        with patch("kpi_metrics.get_session") as mock_session:
            inst = mock_session.return_value
            inst.execute.return_value.fetchall.side_effect = [
                [MagicMock()], [], [MagicMock()]
            ]
            tables = kpi_metrics.get_kpi_monthly_tables(date(2026, 6, 1))
            assert [t["month_label"] for t in tables] == ["Jun '26", "Jun '25"]

    def test_no_data_returns_empty_list(self):
        with patch("kpi_metrics.get_session") as mock_session:
            mock_session.return_value.execute.return_value.fetchall.return_value = []
            tables = kpi_metrics.get_kpi_monthly_tables(date(2026, 6, 1))
            assert tables == []
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
& "D:\Primark Report Generator\.venv-win\Scripts\python.exe" -m pytest "D:\Primark Report Generator\tps-pipeline\tests\test_kpi_metrics.py::TestMonthlyTables" -v
```

Expected: FAIL (`get_kpi_monthly_tables` not defined).

- [ ] **Step 3: Implement**

Append to `tps-pipeline/kpi_metrics.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Same command as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tps-pipeline/kpi_metrics.py tps-pipeline/tests/test_kpi_metrics.py
git commit -m "feat: add kpi monthly country tables metric"
```

---

### Task 5: `get_kpi_approved_by_performance`

**Files:**
- Modify: `tps-pipeline/kpi_metrics.py` (append)
- Test: `tps-pipeline/tests/test_kpi_metrics.py` (append class `TestApprovedByPerformance`)

**Interfaces:**
- Consumes: Task 3 helpers
- Produces: `get_kpi_approved_by_performance(report_month: date) -> dict` — `{"month_labels": [str, str, str], "rows": [{"approved_by": str, "lines": [int, int, int]}]}` (lines = counts for M, M-1, M-last-year)

- [ ] **Step 1: Write the failing tests**

```python
class TestApprovedByPerformance:
    def test_merges_approved_by_across_three_months(self):
        with patch("kpi_metrics.get_session") as mock_session:
            inst = mock_session.return_value
            def fake_row(name, lines):
                row = MagicMock()
                row.approved_by, row.lines = name, lines
                return row
            inst.execute.return_value.fetchall.side_effect = [
                [fake_row("Alice", 5), fake_row("Bob", 3)],
                [fake_row("Alice", 7)],
                [fake_row("Bob", 9)],
            ]
            result = kpi_metrics.get_kpi_approved_by_performance(date(2026, 6, 1))
            assert result["month_labels"] == ["Jun '26", "May '26", "Jun '25"]
            by_name = {r["approved_by"]: r["lines"] for r in result["rows"]}
            assert by_name["Alice"] == [5, 7, 0]
            assert by_name["Bob"] == [3, 0, 9]

    def test_no_data_returns_empty_rows(self):
        with patch("kpi_metrics.get_session") as mock_session:
            mock_session.return_value.execute.return_value.fetchall.return_value = []
            result = kpi_metrics.get_kpi_approved_by_performance(date(2026, 6, 1))
            assert result["rows"] == []
            assert len(result["month_labels"]) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
& "D:\Primark Report Generator\.venv-win\Scripts\python.exe" -m pytest "D:\Primark Report Generator\tps-pipeline\tests\test_kpi_metrics.py::TestApprovedByPerformance" -v
```

Expected: FAIL (`get_kpi_approved_by_performance` not defined).

- [ ] **Step 3: Implement**

Append to `tps-pipeline/kpi_metrics.py`:

```python
def get_kpi_approved_by_performance(report_month: date) -> dict:
    session = get_session()
    try:
        months = get_kpi_table_months(report_month)
        labels = [month_label(m) for m in months]
        counts: dict[str, list[int]] = {}
        for i, m in enumerate(months):
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
                counts.setdefault(r.approved_by, [0, 0, 0])[i] = r.lines
        rows_out = [
            {"approved_by": name, "lines": lines}
            for name, lines in sorted(counts.items())
        ]
        return {"month_labels": labels, "rows": rows_out}
    finally:
        session.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Same command as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tps-pipeline/kpi_metrics.py tps-pipeline/tests/test_kpi_metrics.py
git commit -m "feat: add kpi approved-by performance metric"
```

---

### Task 6: `get_kpi_avg_lines_per_day`

**Files:**
- Modify: `tps-pipeline/kpi_metrics.py` (append)
- Test: `tps-pipeline/tests/test_kpi_metrics.py` (append class `TestAvgLinesPerDay`)

**Interfaces:**
- Consumes: Task 3 helpers
- Produces: `get_kpi_avg_lines_per_day(report_month: date) -> dict` — `{"bd": {"region": "BD", "lines": int, "working_days": int, "avg": float}, "cn": {"region": "CN", "lines": int, "working_days": int, "avg": float}}` for month M. BD = countries in `BD_REGION_COUNTRIES`, CN = all others (`NOT IN`). Both exclude `packaging_status = 'Pending'`. BD days exclude Fri+Sat; CN days exclude Sat+Sun. `avg = round(lines / working_days, 2)` (0.0 if days == 0).

- [ ] **Step 1: Write the failing tests**

```python
class TestAvgLinesPerDay:
    def test_calculation_for_march_2026(self):
        with patch("kpi_metrics.get_session") as mock_session:
            inst = mock_session.return_value
            def fake_row(val):
                row = MagicMock()
                row.__getitem__ = lambda self, key: val
                return row
            inst.execute.return_value.fetchone.side_effect = [fake_row(230), fake_row(154)]
            result = kpi_metrics.get_kpi_avg_lines_per_day(date(2026, 3, 1))
            assert result["bd"]["working_days"] == 23
            assert result["cn"]["working_days"] == 22
            assert result["bd"]["lines"] == 230
            assert result["cn"]["lines"] == 154
            assert result["bd"]["avg"] == round(230 / 23, 2)
            assert result["cn"]["avg"] == round(154 / 22, 2)

    def test_no_data_returns_zero(self):
        with patch("kpi_metrics.get_session") as mock_session:
            mock_session.return_value.execute.return_value.fetchone.return_value = None
            result = kpi_metrics.get_kpi_avg_lines_per_day(date(2026, 3, 1))
            assert result["bd"]["lines"] == 0
            assert result["bd"]["avg"] == 0.0
            assert result["cn"]["lines"] == 0
            assert result["cn"]["avg"] == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
& "D:\Primark Report Generator\.venv-win\Scripts\python.exe" -m pytest "D:\Primark Report Generator\tps-pipeline\tests\test_kpi_metrics.py::TestAvgLinesPerDay" -v
```

Expected: FAIL (`get_kpi_avg_lines_per_day` not defined).

- [ ] **Step 3: Implement**

Append to `tps-pipeline/kpi_metrics.py`:

```python
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
                "avg": round(bd_lines / bd_days, 2) if bd_days else 0.0,
            },
            "cn": {
                "region": "CN",
                "lines": cn_lines,
                "working_days": cn_days,
                "avg": round(cn_lines / cn_days, 2) if cn_days else 0.0,
            },
        }
    finally:
        session.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Same command as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tps-pipeline/kpi_metrics.py tps-pipeline/tests/test_kpi_metrics.py
git commit -m "feat: add kpi avg lines per day metric"
```

---

### Task 7: 12-month trend + region reflected lines

**Files:**
- Modify: `tps-pipeline/kpi_metrics.py` (append)
- Test: `tps-pipeline/tests/test_kpi_metrics.py` (append classes `TestSupplierFactoryTrend`, `TestRegionReflectedLines`)

**Interfaces:**
- Consumes: Task 3 helpers
- Produces:
  - `get_kpi_supplier_factory_trend(report_month: date) -> dict` — `{"labels": [str], "suppliers": [int], "factories": [int]}` (12 months ending at M)
  - `get_kpi_region_reflected_lines(report_month: date) -> dict` — `{"labels": [str], "bd": [int], "cn": [int]}` (reflected lines per month by region, same 12-month range)

- [ ] **Step 1: Write the failing tests**

```python
class TestSupplierFactoryTrend:
    def test_returns_counts_per_month(self):
        with patch("kpi_metrics.get_session") as mock_session, \
             patch("kpi_metrics.get_kpi_chart_months") as mock_range:
            mock_range.return_value = [date(2026, 5, 1), date(2026, 6, 1)]
            inst = mock_session.return_value
            def fake_row(s, f):
                row = MagicMock()
                row.suppliers, row.factories = s, f
                return row
            inst.execute.return_value.fetchone.side_effect = [fake_row(10, 15), fake_row(12, 18)]
            result = kpi_metrics.get_kpi_supplier_factory_trend(date(2026, 6, 1))
            assert result["labels"] == ["May '26", "Jun '26"]
            assert result["suppliers"] == [10, 12]
            assert result["factories"] == [15, 18]

    def test_no_data_returns_zeros(self):
        with patch("kpi_metrics.get_session") as mock_session, \
             patch("kpi_metrics.get_kpi_chart_months") as mock_range:
            mock_range.return_value = [date(2026, 6, 1)]
            mock_session.return_value.execute.return_value.fetchone.return_value = None
            result = kpi_metrics.get_kpi_supplier_factory_trend(date(2026, 6, 1))
            assert result["suppliers"] == [0]
            assert result["factories"] == [0]


class TestRegionReflectedLines:
    def test_classifies_countries_per_month(self):
        with patch("kpi_metrics.get_session") as mock_session, \
             patch("kpi_metrics.get_kpi_chart_months") as mock_range:
            mock_range.return_value = [date(2026, 5, 1), date(2026, 6, 1)]
            inst = mock_session.return_value
            def fake_row(country, lines):
                row = MagicMock()
                row.country, row.lines = country, lines
                return row
            inst.execute.return_value.fetchall.side_effect = [
                [fake_row("Bangladesh", 10), fake_row("China", 5)],
                [fake_row("India", 8), fake_row("Cambodia", 2)],
            ]
            result = kpi_metrics.get_kpi_region_reflected_lines(date(2026, 6, 1))
            assert result["labels"] == ["May '26", "Jun '26"]
            assert result["bd"] == [10, 8]
            assert result["cn"] == [5, 2]

    def test_empty_months_zero(self):
        with patch("kpi_metrics.get_session") as mock_session, \
             patch("kpi_metrics.get_kpi_chart_months") as mock_range:
            mock_range.return_value = [date(2026, 6, 1)]
            mock_session.return_value.execute.return_value.fetchall.return_value = []
            result = kpi_metrics.get_kpi_region_reflected_lines(date(2026, 6, 1))
            assert result["bd"] == [0]
            assert result["cn"] == [0]
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
& "D:\Primark Report Generator\.venv-win\Scripts\python.exe" -m pytest "D:\Primark Report Generator\tps-pipeline\tests\test_kpi_metrics.py::TestSupplierFactoryTrend" "D:\Primark Report Generator\tps-pipeline\tests\test_kpi_metrics.py::TestRegionReflectedLines" -v
```

Expected: FAIL (`get_kpi_supplier_factory_trend` / `get_kpi_region_reflected_lines` not defined).

- [ ] **Step 3: Implement**

Append to `tps-pipeline/kpi_metrics.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Same command as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tps-pipeline/kpi_metrics.py tps-pipeline/tests/test_kpi_metrics.py
git commit -m "feat: add kpi trend and region reflected lines metrics"
```

---

### Task 8: KPI report template

**Files:**
- Create: `tps-pipeline/templates/kpi_report.html.j2`

**Interfaces:**
- Consumes: context from Task 9: `month_name`, `year`, `release_date`, `monthly_tables`, `performance`, `avg_per_day`, `trend`, `region_lines`, `primark_logo`, `allport_logo`
- Produces: full HTML document (portrait A4) with header (same style as TPS: logos + red accent bar), title "Transit Packaging System (TPS) KPI Report", 3 optional monthly tables, approved-by performance table, avg-lines-per-day BD/CN blocks, 3 Chart.js line charts

- [ ] **Step 1: Write the template**

`tps-pipeline/templates/kpi_report.html.j2` (full content):

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Inter', -apple-system, sans-serif; font-size: 12px; color: #1a1a1a; background: #e5e7eb; }
    @page { size: A4 portrait; margin: 0; }
    .page { width: 210mm; min-height: 297mm; background: white; margin: 0 auto 5px auto; display: flex; flex-direction: column; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .page-header { display: flex; justify-content: space-between; align-items: center; padding: 6px 14px; border-bottom: 4px solid #e31837; background: white; }
    .brand-img-primark { height: 25px; width: auto; }
    .brand-img-allport { height: 28px; width: auto; }
    .page-content { flex: 1; padding: 12px 18px; }
    .report-title-block { text-align: center; margin-bottom: 10px; }
    .report-title-main { font-size: 22px; font-weight: 800; color: #1B2838; letter-spacing: -0.3px; }
    .report-title-sub { font-size: 12px; font-weight: 600; color: #6B7280; text-transform: uppercase; letter-spacing: 1px; margin-top: 2px; }
    .report-period { font-size: 15px; color: #9ca3af; margin-top: 2px; }
    .section-header { display: flex; align-items: center; gap: 10px; margin: 12px 0 6px; }
    .section-title { font-size: 12px; font-weight: 700; color: #1B2838; text-transform: uppercase; letter-spacing: 0.5px; }
    .section-line { flex: 1; height: 2px; background: #E5E7EB; }
    table { width: 100%; border-collapse: collapse; font-size: 9px; margin-bottom: 10px; }
    thead { background: #1B2838; color: white; }
    th { font-weight: 600; text-transform: uppercase; font-size: 7px; letter-spacing: 0.3px; padding: 4px 6px; text-align: left; }
    th.text-right, td.text-right { text-align: right; }
    td { padding: 3px 6px; border-bottom: 1px solid #e5e7eb; color: #374151; }
    tbody tr:nth-child(even) { background: #f9fafb; }
    tr.total-row td { background: #f3f4f6; border-top: 2px solid #1B2838; font-weight: 600; }
    .avg-blocks { display: flex; gap: 10px; margin-bottom: 10px; }
    .avg-block { flex: 1; border: 1px solid #e5e7eb; border-radius: 10px; padding: 10px; }
    .avg-block-title { font-size: 9px; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
    .avg-value { font-size: 22px; font-weight: 800; color: #1B2838; }
    .avg-meta { font-size: 9px; color: #6b7280; margin-top: 2px; }
    .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .chart-box { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 10px; padding: 10px; height: 260px; }
    .chart-box-full { grid-column: 1 / -1; }
    .chart-box-title { font-size: 9px; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; text-align: center; }
    .chart-box canvas { width: 100% !important; height: calc(100% - 24px) !important; }
    .page-footer { display: flex; justify-content: space-between; padding: 6px 16px; border-top: 1px solid #e5e7eb; font-size: 8px; color: #6b7280; background: #f9fafb; }
  </style>
</head>
<body>
<div class="page">
  <div class="page-header">
    <img class="brand-img-primark" src="{{ primark_logo }}" alt="Primark">
    <img class="brand-img-allport" src="{{ allport_logo }}" alt="Allport Pacd">
  </div>

  <div class="page-content">
    <div class="report-title-block">
      <div class="report-title-main">Transit Packaging System (TPS) KPI Report</div>
      <div class="report-period">{{ month_name }} {{ year }}</div>
    </div>

    {% for table in monthly_tables %}
    <div class="section-header">
      <span class="section-title">Monthly Summary — {{ table.month_label }}</span>
      <div class="section-line"></div>
    </div>
    <table>
      <thead>
        <tr>
          <th>Country</th>
          <th class="text-right">No. of Suppliers</th>
          <th class="text-right">No. of Factories</th>
          <th class="text-right">Reflected Lines</th>
        </tr>
      </thead>
      <tbody>
        {% for row in table.rows %}
        <tr>
          <td>{{ row.country }}</td>
          <td class="text-right">{{ row.suppliers }}</td>
          <td class="text-right">{{ row.factories }}</td>
          <td class="text-right">{{ row.reflected_lines }}</td>
        </tr>
        {% endfor %}
        <tr class="total-row">
          <td>Total</td>
          <td class="text-right">{{ table.totals.suppliers }}</td>
          <td class="text-right">{{ table.totals.factories }}</td>
          <td class="text-right">{{ table.totals.reflected_lines }}</td>
        </tr>
      </tbody>
    </table>
    {% endfor %}

    <div class="section-header">
      <span class="section-title">Individual Performance (Approved By)</span>
      <div class="section-line"></div>
    </div>
    <table>
      <thead>
        <tr>
          <th>Approved By</th>
          {% for label in performance.month_labels %}
          <th class="text-right">{{ label }}</th>
          {% endfor %}
        </tr>
      </thead>
      <tbody>
        {% for row in performance.rows %}
        <tr>
          <td>{{ row.approved_by }}</td>
          {% for count in row.lines %}
          <td class="text-right">{{ count }}</td>
          {% endfor %}
        </tr>
        {% else %}
        <tr><td colspan="{{ 1 + performance.month_labels|length }}">No approved-by data available.</td></tr>
        {% endfor %}
      </tbody>
    </table>

    <div class="section-header">
      <span class="section-title">Average Lines Processed Per Day — {{ month_name }} {{ year }}</span>
      <div class="section-line"></div>
    </div>
    <div class="avg-blocks">
      <div class="avg-block">
        <div class="avg-block-title">BD Region</div>
        <div class="avg-value">{{ avg_per_day.bd.avg }}</div>
        <div class="avg-meta">{{ avg_per_day.bd.lines }} lines / {{ avg_per_day.bd.working_days }} working days</div>
      </div>
      <div class="avg-block">
        <div class="avg-block-title">CN Region</div>
        <div class="avg-value">{{ avg_per_day.cn.avg }}</div>
        <div class="avg-meta">{{ avg_per_day.cn.lines }} lines / {{ avg_per_day.cn.working_days }} working days</div>
      </div>
    </div>

    <div class="section-header">
      <span class="section-title">12-Month Trend</span>
      <div class="section-line"></div>
    </div>
    <div class="charts-row">
      <div class="chart-box chart-box-full">
        <div class="chart-box-title">Suppliers & Factories (Last 12 Months)</div>
        <canvas id="chartTrend"></canvas>
      </div>
      <div class="chart-box">
        <div class="chart-box-title">Reflected Lines — BD Region</div>
        <canvas id="chartBdLines"></canvas>
      </div>
      <div class="chart-box">
        <div class="chart-box-title">Reflected Lines — CN Region</div>
        <canvas id="chartCnLines"></canvas>
      </div>
    </div>
  </div>

  <div class="page-footer">
    <span>Generated: {{ release_date }}</span>
    <span>TPS KPI Report</span>
  </div>
</div>

<script>
window.addEventListener('load', function() {
  const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { display: true, labels: { font: { size: 9, family: 'Arial' } } } },
    elements: { point: { radius: 3 } },
    scales: {
      x: { ticks: { font: { size: 9, family: 'Arial' }, color: '#374151', maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }, grid: { display: false } },
      y: { ticks: { font: { size: 9, family: 'Arial' }, color: '#374151' }, grid: { color: '#f3f4f6' }, beginAtZero: true }
    }
  };

  new Chart(document.getElementById('chartTrend'), {
    type: 'line',
    data: {
      labels: {{ trend.labels|tojson }},
      datasets: [
        { label: 'Suppliers', data: {{ trend.suppliers }}, borderColor: '#4A90D9', backgroundColor: 'transparent', tension: 0.4, fill: false },
        { label: 'Factories', data: {{ trend.factories }}, borderColor: '#e31837', backgroundColor: 'transparent', tension: 0.4, fill: false }
      ]
    },
    options: chartDefaults
  });

  new Chart(document.getElementById('chartBdLines'), {
    type: 'line',
    data: {
      labels: {{ region_lines.labels|tojson }},
      datasets: [{ label: 'BD Region', data: {{ region_lines.bd }}, borderColor: '#059669', backgroundColor: 'transparent', tension: 0.4, fill: false }]
    },
    options: chartDefaults
  });

  new Chart(document.getElementById('chartCnLines'), {
    type: 'line',
    data: {
      labels: {{ region_lines.labels|tojson }},
      datasets: [{ label: 'CN Region', data: {{ region_lines.cn }}, borderColor: '#ea580c', backgroundColor: 'transparent', tension: 0.4, fill: false }]
    },
    options: chartDefaults
  });
});
</script>
</body>
</html>
```

- [ ] **Step 2: Verify template renders without Jinja errors**

```powershell
& "D:\Primark Report Generator\.venv-win\Scripts\python.exe" -c "import sys; sys.path.insert(0, r'D:\Primark Report Generator\tps-pipeline'); from jinja2 import Environment, FileSystemLoader, select_autoescape; from pathlib import Path; env = Environment(loader=FileSystemLoader(r'D:\Primark Report Generator\tps-pipeline\templates'), autoescape=select_autoescape(['html','xml'])); t = env.get_template('kpi_report.html.j2'); t.render(month_name='June', year=2026, release_date='04 Aug 2026', monthly_tables=[], performance={'month_labels': ['A','B','C'], 'rows': []}, avg_per_day={'bd': {'avg': 1.0, 'lines': 10, 'working_days': 20}, 'cn': {'avg': 2.0, 'lines': 20, 'working_days': 20}}, trend={'labels': ['x'], 'suppliers': [1], 'factories': [1]}, region_lines={'labels': ['x'], 'bd': [1], 'cn': [1]}, primark_logo='x', allport_logo='x'); print('OK')"
```

Expected: prints `OK`.

- [ ] **Step 3: Commit**

```bash
git add tps-pipeline/templates/kpi_report.html.j2
git commit -m "feat: add kpi report template"
```

---

### Task 9: `kpi_renderer.py`

**Files:**
- Create: `tps-pipeline/kpi_renderer.py`
- Test: `tps-pipeline/tests/test_kpi_renderer.py` (create)

**Interfaces:**
- Consumes: `kpi_metrics` functions from Tasks 4-7, `metrics.get_report_month`, `renderer` logo-loading pattern (re-implement local `_load_logo`; do NOT import from renderer)
- Produces: `render_kpi_report(report_month: date | None = None) -> str` (full HTML). Raises `ValueError("No data available for the KPI report in the selected month.")` when there is no data at all.

- [ ] **Step 1: Write the failing test**

`tps-pipeline/tests/test_kpi_renderer.py`:

```python
import sys
sys.path.insert(0, "..")

from datetime import date
from unittest.mock import patch, MagicMock

import pytest

import kpi_renderer


@pytest.fixture
def mock_metrics():
    with patch.multiple(
        "kpi_renderer",
        get_kpi_monthly_tables=MagicMock(return_value=[]),
        get_kpi_approved_by_performance=MagicMock(
            return_value={"month_labels": ["Jun '26", "May '26", "Jun '25"], "rows": []}
        ),
        get_kpi_avg_lines_per_day=MagicMock(
            return_value={
                "bd": {"region": "BD", "lines": 230, "working_days": 23, "avg": 10.0},
                "cn": {"region": "CN", "lines": 154, "working_days": 22, "avg": 7.0},
            }
        ),
        get_kpi_supplier_factory_trend=MagicMock(
            return_value={"labels": ["Jun '26"], "suppliers": [10], "factories": [15]}
        ),
        get_kpi_region_reflected_lines=MagicMock(
            return_value={"labels": ["Jun '26"], "bd": [100], "cn": [50]}
        ),
    ):
        yield


class TestRenderKpiReport:
    def test_renders_full_html(self, mock_metrics):
        html = kpi_renderer.render_kpi_report(date(2026, 6, 1))
        assert "Transit Packaging System (TPS) KPI Report" in html
        assert "Individual Performance" in html
        assert "Average Lines Processed Per Day" in html
        assert "chartTrend" in html

    def test_raises_when_no_data(self):
        with patch.multiple(
            "kpi_renderer",
            get_kpi_monthly_tables=MagicMock(return_value=[]),
            get_kpi_approved_by_performance=MagicMock(return_value={"month_labels": [], "rows": []}),
            get_kpi_avg_lines_per_day=MagicMock(
                return_value={
                    "bd": {"region": "BD", "lines": 0, "working_days": 23, "avg": 0.0},
                    "cn": {"region": "CN", "lines": 0, "working_days": 22, "avg": 0.0},
                }
            ),
            get_kpi_supplier_factory_trend=MagicMock(return_value={"labels": [], "suppliers": [], "factories": []}),
            get_kpi_region_reflected_lines=MagicMock(return_value={"labels": [], "bd": [], "cn": []}),
        ):
            with pytest.raises(ValueError, match="No data available"):
                kpi_renderer.render_kpi_report(date(2026, 6, 1))
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
& "D:\Primark Report Generator\.venv-win\Scripts\python.exe" -m pytest "D:\Primark Report Generator\tps-pipeline\tests\test_kpi_renderer.py" -v
```

Expected: FAIL with ImportError (`kpi_renderer` not found).

- [ ] **Step 3: Implement**

`tps-pipeline/kpi_renderer.py`:

```python
import base64
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from kpi_metrics import (
    get_kpi_approved_by_performance,
    get_kpi_avg_lines_per_day,
    get_kpi_monthly_tables,
    get_kpi_region_reflected_lines,
    get_kpi_supplier_factory_trend,
)
from metrics import get_report_month

ASSETS_PATH = Path(__file__).parent / "assets"


def _load_logo(name: str) -> str:
    with open(ASSETS_PATH / name, "rb") as f:
        return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"


PRIMARK_LOGO = _load_logo("Primark-logo.png")
ALLPORT_LOGO = _load_logo("allport-pacd-logo.png")


def render_kpi_report(report_month: date | None = None) -> str:
    if report_month is None:
        report_month = get_report_month()

    monthly_tables = get_kpi_monthly_tables(report_month)
    performance = get_kpi_approved_by_performance(report_month)
    avg_per_day = get_kpi_avg_lines_per_day(report_month)
    trend = get_kpi_supplier_factory_trend(report_month)
    region_lines = get_kpi_region_reflected_lines(report_month)

    has_data = (
        bool(monthly_tables)
        or bool(performance["rows"])
        or avg_per_day["bd"]["lines"] > 0
        or avg_per_day["cn"]["lines"] > 0
    )
    if not has_data:
        raise ValueError("No data available for the KPI report in the selected month.")

    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"])
    )
    template = env.get_template("kpi_report.html.j2")

    context = {
        "month_name": report_month.strftime("%B"),
        "year": report_month.year,
        "release_date": datetime.now().strftime("%d %B %Y"),
        "monthly_tables": monthly_tables,
        "performance": performance,
        "avg_per_day": avg_per_day,
        "trend": trend,
        "region_lines": region_lines,
        "primark_logo": PRIMARK_LOGO,
        "allport_logo": ALLPORT_LOGO,
    }
    return template.render(**context)
```

- [ ] **Step 4: Run test to verify it passes**

Same command as Step 2. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tps-pipeline/kpi_renderer.py tps-pipeline/tests/test_kpi_renderer.py
git commit -m "feat: add kpi report renderer"
```

---

### Task 10: Menu integration (KPI report + Clear Database)

**Files:**
- Modify: `tps-pipeline/menu.py` (only: import line, banner, two new handler functions, two new `main()` branches)

**Interfaces:**
- Consumes: `database.clear_all_tables` (Task 2), `kpi_renderer.render_kpi_report` (Task 9), `pdfgen.html_to_pdf`, existing `config.yaml`/`safe_filename` patterns
- Produces: menu options `[7] Generate KPI Report`, `[8] Clear Database`

- [ ] **Step 1: Write the failing test**

`tps-pipeline/tests/test_menu.py`:

```python
import sys
sys.path.insert(0, "..")

from datetime import date
from unittest.mock import patch, MagicMock

import pytest

import menu


class TestMenuBanner:
    def test_banner_has_new_options(self, capsys):
        menu.print_banner()
        out = capsys.readouterr().out
        assert "[7] Generate KPI Report" in out
        assert "[8] Clear Database" in out


class TestClearDatabaseHandler:
    def test_clears_with_confirmation(self, capsys):
        with patch("menu.clear_all_tables") as mock_clear, \
             patch("builtins.input", return_value="y"):
            menu.handle_clear_database()
            mock_clear.assert_called_once()

    def test_aborts_without_confirmation(self, capsys):
        with patch("menu.clear_all_tables") as mock_clear, \
             patch("builtins.input", return_value="n"):
            menu.handle_clear_database()
            mock_clear.assert_not_called()


class TestKpiReportHandler:
    def test_generates_pdf(self):
        fake_html = "<html>KPI</html>"
        with patch("menu.render_kpi_report", return_value=fake_html) as mock_render, \
             patch("menu.html_to_pdf", return_value=True) as mock_pdf, \
             patch("menu.input", side_effect=["2026", "6"]):
            menu.handle_generate_kpi_report()
            mock_render.assert_called_once()
            mock_pdf.assert_called_once()
            assert "KPI_Report" in str(mock_pdf.call_args[0][1])

    def test_no_data_prints_message(self, capsys):
        with patch("menu.render_kpi_report", side_effect=ValueError("No data available")), \
             patch("menu.html_to_pdf") as mock_pdf, \
             patch("menu.input", side_effect=["2026", "6"]):
            menu.handle_generate_kpi_report()
            mock_pdf.assert_not_called()
            assert "No data" in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

```powershell
& "D:\Primark Report Generator\.venv-win\Scripts\python.exe" -m pytest "D:\Primark Report Generator\tps-pipeline\tests\test_menu.py" -v
```

Expected: FAIL (functions/options missing).

- [ ] **Step 3: Implement the imports**

In `tps-pipeline/menu.py`, change the import line 8 from:

```python
from database import get_session, text, clear_supplier_emails, insert_supplier_email, init_supplier_emails_table
```

to:

```python
from database import get_session, text, clear_supplier_emails, clear_all_tables, insert_supplier_email, init_supplier_emails_table
```

And after the `summary_excel_renderer` import add:

```python
from kpi_renderer import render_kpi_report
```

- [ ] **Step 4: Implement the banner**

Replace the banner text in `print_banner()` (lines ~36-50) with:

```python
def print_banner():
    banner = """
============================================
   TPS Compliance Report Generator
============================================
   [1] Process New File
   [2] Generate Reports
   [3] Generate Summary Report
   [4] View Logs
   [5] Extract Supplier Data
   [6] Import Supplier Emails
   [7] Generate KPI Report
   [8] Clear Database
   [0] Exit
============================================
    """
    print(banner)
```

- [ ] **Step 5: Implement the two handlers**

Add before `main()` in `tps-pipeline/menu.py`:

```python
def handle_generate_kpi_report():
    config_path = Path(__file__).parent / "config.yaml"
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return
    output_dir = Path(__file__).parent / config["paths"]["output_dir"]
    output_dir.mkdir(exist_ok=True)

    print("\n=== KPI Report Month Selection ===")
    print("Enter year and month for the report (or press Enter for default: previous month)")
    year_input = input("Year (e.g., 2026) [default: previous month]: ").strip()
    month_input = input("Month (1-12) [default: previous month]: ").strip()

    report_month = None
    if month_input:
        try:
            year = int(year_input) if year_input else date.today().year
            month = int(month_input)
            report_month = date(year, month, 1)
            print(f"Using specified month: {report_month.strftime('%B %Y')}")
        except ValueError:
            print("Invalid date. Using default.")
            report_month = None

    if report_month is None:
        print("Using default report month.")
        today = date.today()
        year = today.year if today.month > 1 else today.year - 1
        month = today.month - 1 if today.month > 1 else 12
        report_month = date(year, month, 1)

    print("Rendering KPI report...")
    try:
        html = render_kpi_report(report_month)

        file_date = report_month.strftime("%B_%Y")
        output_path = output_dir / f"KPI_Report_{file_date}.pdf"

        if output_path.exists():
            output_path.unlink()

        html_to_pdf(html, str(output_path))
        logger.info(f"KPI report saved: {output_path}")
        print(f"KPI report generated: {output_path}")
    except ValueError as e:
        logger.warning(f"KPI report skipped: {e}")
        print(f"KPI report skipped: {e}")
    except Exception as e:
        logger.error(f"Error generating KPI report: {e}")
        print(f"Error generating KPI report: {e}")


def handle_clear_database():
    print("\n=== Clear Database ===")
    response = input("This will DELETE ALL rows from raw_data and supplier_emails (tables are kept). Continue? (y/n): ").strip().lower()
    if response != "y":
        print("Canceled.")
        return
    try:
        clear_all_tables()
        logger.info("Database cleared: all rows removed from raw_data and supplier_emails")
        print("Database cleared: all rows removed. Tables preserved.")
    except Exception as e:
        logger.error(f"Error clearing database: {e}")
        print(f"Error clearing database: {e}")
```

- [ ] **Step 6: Implement the menu branches**

In `main()`, replace the branch block:

```python
        elif choice == "6":
            handle_import_emails()
        elif choice == "0":
```

with:

```python
        elif choice == "6":
            handle_import_emails()
        elif choice == "7":
            handle_generate_kpi_report()
        elif choice == "8":
            handle_clear_database()
        elif choice == "0":
```

- [ ] **Step 7: Run tests to verify they pass**

```powershell
& "D:\Primark Report Generator\.venv-win\Scripts\python.exe" -m pytest "D:\Primark Report Generator\tps-pipeline\tests" -v
```

Expected: ALL tests pass (existing + new).

- [ ] **Step 8: Commit**

```bash
git add tps-pipeline/menu.py tps-pipeline/tests/test_menu.py
git commit -m "feat: add kpi report and clear database menu options"
```

---

### Task 11: End-to-end manual verification

**Files:** none (verification only)

**Interfaces:**
- Consumes: everything from Tasks 1-10

- [ ] **Step 1: Generate the KPI report PDF**

Run the menu non-interactively is not possible (input prompts), so verify via a small script instead (workdir `tps-pipeline`):

```powershell
& "D:\Primark Report Generator\.venv-win\Scripts\python.exe" -c "import sys; sys.path.insert(0, '.'); from kpi_renderer import render_kpi_report; from pdfgen import html_to_pdf; from datetime import date; html = render_kpi_report(date(2026, 6, 1)); html_to_pdf(html, 'output/KPI_Report_June_2026.pdf'); print('PDF written')"
```

Expected: prints `PDF written`; `tps-pipeline/output/KPI_Report_June_2026.pdf` exists. (Note: first run downloads/launches Chromium via Playwright — if `playwright install chromium` was not run in Task 1, run it now.)

- [ ] **Step 2: Verify the PDF contents**

Open `output/KPI_Report_June_2026.pdf`. Confirm: header logos, title "Transit Packaging System (TPS) KPI Report", monthly summary tables (only months with data), individual performance table, BD/CN avg lines/day blocks, 3 charts.

- [ ] **Step 3: Verify Clear Database flow**

```powershell
& "D:\Primark Report Generator\.venv-win\Scripts\python.exe" -c "import sys; sys.path.insert(0, '.'); from database import clear_all_tables, get_session; from sqlalchemy import text; clear_all_tables(); s = get_session(); print('raw_data rows:', s.execute(text('SELECT COUNT(*) FROM raw_data')).scalar()); print('supplier_emails rows:', s.execute(text('SELECT COUNT(*) FROM supplier_emails')).scalar()); s.close()"
```

Expected: both counts are 0, and no error (tables still exist).

- [ ] **Step 4: Restore data if needed**

If the DB data was needed for other work, re-import via menu option 1 (`Process New File`) with the original Excel files. If this was intentional (user wanted DB cleared), skip.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: verification adjustments"
```

---

## Self-Review

**Spec coverage:**
- Clear Database (delete rows, keep tables) → Task 2 + Task 10 ✔
- KPI PDF, same header, title "Transit Packaging System (TPS) KPI Report" → Task 8/9 ✔
- 3 monthly tables (M, M-1, M-last-year), skip empty → Task 4 ✔
- Individual performance (approved_by, 3 month columns) → Task 5 ✔
- Avg lines/day, BD 6 countries, CN others, not-Pending, BD Fri+Sat / CN Sat+Sun working days → Task 6 ✔
- 12-month supplier/factory line chart → Task 7 ✔
- BD region reflected lines by month → Task 7 ✔
- CN region reflected lines by month → Task 7 ✔
- Month selection same pattern as TPS → Task 10 ✔
- PDF via pdfgen → Task 10 ✔
- No-data abort → Task 9 (ValueError) + Task 10 (caught, message) ✔
- Output path `output/KPI_Report_<Month>.pdf` → Task 10 ✔

**Placeholder scan:** every step has concrete code or an exact command; no TBD/TODO. ✔

**Type consistency:** `get_kpi_monthly_tables`/`get_kpi_approved_by_performance`/`get_kpi_avg_lines_per_day`/`get_kpi_supplier_factory_trend`/`get_kpi_region_reflected_lines` are defined once in Tasks 4-7 and consumed with identical names in Tasks 9-10. Template context keys match the renderer exactly (`monthly_tables`, `performance`, `avg_per_day`, `trend`, `region_lines`). ✔

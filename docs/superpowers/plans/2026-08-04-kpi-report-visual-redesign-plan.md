# KPI Report Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the KPI report PDF layout — 3 monthly summary cards in one row, simplified Individual Performance title with month-skip rule, ceil-rounded avg lines/day, and charts on their own page.

**Architecture:** Template-only changes in `templates/kpi_report.html.j2` (cards, title, page break, full-width charts) plus two behavior changes in `kpi_metrics.py` (`get_kpi_approved_by_performance` month filtering, `get_kpi_avg_lines_per_day` ceil). Page size stays A4 (already set in `@page` and `pdfgen.html_to_pdf` default).

**Tech Stack:** Jinja2, CSS, Python, SQLAlchemy, Playwright (PDF via existing `pdfgen.html_to_pdf`).

## Global Constraints

- Environment: Windows + PowerShell 5.1 (no bash). Test python: `D:\Primark Report Generator\.venv-win\Scripts\python.exe` (quote it). Work from `D:\Primark Report Generator\tps-pipeline`.
- tps-pipeline is its own git repo (nested). Run git with workdir `D:\Primark Report Generator\tps-pipeline`. Use per-command identity: `git -c user.name=Shoaib -c user.email=shoaib@local commit -m "<message>"`. Stage ONLY the files named in the task. Do NOT stage or modify any other file.
- menu.py currently has pre-existing uncommitted WIP — never touch it in these tasks.
- Design doc: `docs/superpowers/specs/2026-08-04-kpi-report-visual-redesign-design.md` (in OUTER repo, commit 4a5a808).
- Existing files to read for context: `templates/kpi_report.html.j2`, `kpi_metrics.py`, `tests/test_kpi_metrics.py`, `tests/test_kpi_renderer.py` (all in tps-pipeline).

---
## Task 1: Template redesign (cards, title, charts page)

**Files:**
- Modify: `templates/kpi_report.html.j2`
- Modify: `tests/test_kpi_renderer.py`

**Interfaces:**
- Consumes: context dict from `kpi_renderer.render_kpi_report` — unchanged keys: `month_name`, `year`, `release_date`, `monthly_tables` (list of `{"month_label", "rows", "totals"}`, months with no data already skipped by `get_kpi_monthly_tables`), `performance` (`{"month_labels", "rows"}`, Task 2 makes `month_labels` only months with data), `avg_per_day`, `trend`, `region_lines`, `primark_logo`, `allport_logo`.
- Produces: rendered HTML whose page 1 shows 3 month cards in a row + performance + avg blocks, page 2 shows all 3 charts full-width; section title "Individual Performance" without "(Approved By)".

- [ ] **Step 1: Write the failing test** — update `tests/test_kpi_renderer.py` `test_renders_full_html` with new structural assertions (after the template is changed they pass; before, `month-cards`/`charts-page` fail):

```python
    def test_renders_full_html(self, mock_metrics):
        html = kpi_renderer.render_kpi_report(date(2026, 6, 1))
        assert "Transit Packaging System (TPS) KPI Report" in html
        assert "Individual Performance" in html
        assert "Individual Performance (Approved By)" not in html
        assert "Average Lines Processed Per Day" in html
        assert "month-cards" in html
        assert "month-card-title" in html
        assert "charts-page" in html
        assert "chartTrend" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `..\..\.venv-win\Scripts\python.exe -m pytest tests\test_kpi_renderer.py::TestRenderKpiReport::test_renders_full_html -v`
Expected: FAIL — `"month-cards"` not found in rendered HTML.

- [ ] **Step 3: Modify the template** — in `templates/kpi_report.html.j2`:

1. Add to the `<style>` block (replace the current `.charts-row`/`.chart-box` grid rules; keep `.chart-box-title`):

```css
    .month-cards { display: flex; gap: 10px; margin-bottom: 10px; }
    .month-card { flex: 1; border: 1px solid #e5e7eb; border-radius: 10px; padding: 10px; background: #f9fafb; }
    .month-card-title { font-size: 9px; font-weight: 700; color: #1B2838; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; text-align: center; }
    .month-card table { margin-bottom: 0; font-size: 7px; }
    .month-card th { padding: 3px 4px; }
    .month-card td { padding: 2px 4px; }
    .charts-page { page-break-before: always; }
    .chart-box { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 10px; padding: 10px; height: 260px; margin-bottom: 10px; }
    .chart-box canvas { width: 100% !important; height: calc(100% - 24px) !important; }
```

2. Replace the `{% for table in monthly_tables %}` ... `{% endfor %}` block (lines 56-87) with a single section header plus one row of cards:

```html
    {% if monthly_tables %}
    <div class="section-header">
      <span class="section-title">Monthly Summary</span>
      <div class="section-line"></div>
    </div>
    <div class="month-cards">
      {% for table in monthly_tables %}
      <div class="month-card">
        <div class="month-card-title">{{ table.month_label }}</div>
        <table>
          <thead>
            <tr>
              <th>Country</th>
              <th class="text-right">Suppliers</th>
              <th class="text-right">Factories</th>
              <th class="text-right">Lines</th>
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
      </div>
      {% endfor %}
    </div>
    {% endif %}
```

3. Change the performance section title (line 90) from `Individual Performance (Approved By)` to:

```html
      <span class="section-title">Individual Performance</span>
```

4. Wrap the charts section in a page-break container and stack charts full-width (replace lines 133-150):

```html
    <div class="charts-page">
      <div class="section-header">
        <span class="section-title">12-Month Trend</span>
        <div class="section-line"></div>
      </div>
      <div class="chart-box">
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `..\..\.venv-win\Scripts\python.exe -m pytest tests\test_kpi_renderer.py -v`
Expected: PASS (2 tests). Then full suite: `..\..\.venv-win\Scripts\python.exe -m pytest tests -v` — Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add templates/kpi_report.html.j2 tests/test_kpi_renderer.py
git -c user.name=Shoaib -c user.email=shoaib@local commit -m "feat: redesign kpi report layout with month cards and charts page"
```

---
## Task 2: Metrics — ceil avg and performance month skip

**Files:**
- Modify: `kpi_metrics.py` (imports; `get_kpi_approved_by_performance`; `get_kpi_avg_lines_per_day`)
- Modify: `tests/test_kpi_metrics.py`

**Interfaces:**
- Consumes: `get_kpi_table_months(report_month) -> list[date]`, `get_kpi_monthly_tables(report_month) -> list[dict]`, `month_label(d) -> str`, `get_last_day_of_month` (from metrics), `get_session` — all existing.
- Produces: `get_kpi_approved_by_performance(report_month) -> {"month_labels": list[str], "rows": [{"approved_by": str, "lines": list[int]}]}` where `month_labels` contains ONLY months present in `get_kpi_monthly_tables` (same skip rule, same order M, M-1, M-last-year) and each `lines` list aligns to `month_labels`; `get_kpi_avg_lines_per_day` returns `"avg": math.ceil(lines / working_days)` (int; 0 when working_days == 0).

- [ ] **Step 1: Write the failing tests** — update `tests/test_kpi_metrics.py`:

Replace `TestApprovedByPerformance::test_merges_approved_by_across_three_months` and `test_no_data_returns_empty_rows` with:

```python
    def test_skips_months_without_data(self):
        with patch("kpi_metrics.get_session") as mock_session, \
             patch("kpi_metrics.get_kpi_monthly_tables") as mock_tables:
            mock_tables.return_value = [
                {"month_label": "Jun '26", "rows": [MagicMock()], "totals": {}},
                {"month_label": "May '26", "rows": [MagicMock()], "totals": {}},
            ]
            inst = mock_session.return_value
            def fake_row(name, lines):
                row = MagicMock()
                row.approved_by, row.lines = name, lines
                return row
            inst.execute.return_value.fetchall.side_effect = [
                [fake_row("Alice", 5), fake_row("Bob", 3)],
                [fake_row("Alice", 7)],
            ]
            result = kpi_metrics.get_kpi_approved_by_performance(date(2026, 6, 1))
            assert result["month_labels"] == ["Jun '26", "May '26"]
            by_name = {r["approved_by"]: r["lines"] for r in result["rows"]}
            assert by_name["Alice"] == [5, 7]
            assert by_name["Bob"] == [3, 0]

    def test_no_data_returns_empty_rows_and_labels(self):
        with patch("kpi_metrics.get_session") as mock_session, \
             patch("kpi_metrics.get_kpi_monthly_tables") as mock_tables:
            mock_tables.return_value = []
            result = kpi_metrics.get_kpi_approved_by_performance(date(2026, 6, 1))
            assert result["rows"] == []
            assert result["month_labels"] == []
```

In `TestAvgLinesPerDay::test_calculation_for_march_2026`, change the two avg assertions to ceil-to-int (lines 230 → ceil(230/23) = 10, 154 → ceil(154/22) = 7):

```python
            assert result["bd"]["avg"] == 10
            assert result["cn"]["avg"] == 7
```

Add a new ceil test (non-divisible → rounds up):

```python
    def test_avg_rounds_up_to_whole_number(self):
        with patch("kpi_metrics.get_session") as mock_session:
            inst = mock_session.return_value
            def fake_row(val):
                row = MagicMock()
                row.__getitem__ = lambda self, key: val
                return row
            inst.execute.return_value.fetchone.side_effect = [fake_row(231), fake_row(45)]
            result = kpi_metrics.get_kpi_avg_lines_per_day(date(2026, 3, 1))
            assert result["bd"]["avg"] == 11   # 231/23 = 10.04 → ceil = 11
            assert result["cn"]["avg"] == 3    # 45/22 = 2.045 → ceil = 3
```

Keep `test_no_data_returns_zero` unchanged (`avg == 0.0` still holds; 0 == 0.0).

- [ ] **Step 2: Run tests to verify they fail**

Run: `..\..\.venv-win\Scripts\python.exe -m pytest tests\test_kpi_metrics.py -v`
Expected: FAIL — `TestApprovedByPerformance` has no `test_skips_months_without_data` matching `mock_tables` (old test still expects 3 labels), avg tests assert floats (`round(...)` result 10.0 != 10? note: 10.0 == 10 is True — so the ceil test `test_avg_rounds_up_to_whole_number` is the guaranteed failure).

- [ ] **Step 3: Implement** — in `kpi_metrics.py`:

1. Add `import math` to the imports.

2. Replace `get_kpi_approved_by_performance` entirely:

```python
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
```

3. In `get_kpi_avg_lines_per_day`, change both `"avg"` values from `round(x / days, 2) if days else 0.0` to `math.ceil(x / days) if days else 0`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `..\..\.venv-win\Scripts\python.exe -m pytest tests\test_kpi_metrics.py -v`
Expected: PASS. Then full suite: `..\..\.venv-win\Scripts\python.exe -m pytest tests -v` — Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add kpi_metrics.py tests/test_kpi_metrics.py
git -c user.name=Shoaib -c user.email=shoaib@local commit -m "feat: ceil avg lines per day and skip months without data in performance table"
```

---
## Task 3: End-to-end verification

**Files:** none (no code changes, no commits).

**Interfaces:**
- Consumes: Task 1 template + Task 2 metrics; `menu.handle_generate_kpi_report` / `kpi_renderer.render_kpi_report` + `pdfgen.html_to_pdf`; PostgreSQL 16 (`C:\Program Files\PostgreSQL\16\bin\psql.exe`, db `tps_compliance`, user `postgres`, password `postgres`, `$env:PGPASSWORD = "postgres"`).

- [ ] **Step 1: Check database state** — the DB was emptied by a previous clear-db test.

Run (workdir `D:\Primark Report Generator\tps-pipeline`):
```powershell
$env:PGPASSWORD = "postgres"; & "C:\Program Files\PostgreSQL\16\bin\psql.exe" -h localhost -U postgres -d tps_compliance -t -c "SELECT COUNT(*) FROM raw_data;"
```
Expected: > 0 (user has re-imported). If 0, report BLOCKED and ask the user to re-import via menu option 1.

- [ ] **Step 2: Regenerate the PDF** — via the same render path menu.py uses. Run from `tps-pipeline`:

```powershell
..\..\.venv-win\Scripts\python.exe -c "import sys; sys.path.insert(0, '.'); import kpi_renderer, pdfgen; from pathlib import Path; import os; os.chdir(r'D:\Primark Report Generator\tps-pipeline'); html = kpi_renderer.render_kpi_report(); out = r'D:\Primark Report Generator\tps-pipeline\output\KPI_Report_Visual_Check.pdf'; Path(out).unlink(missing_ok=True); print('PDF written' if pdfgen.html_to_pdf(html, out) else 'FAILED')"
```
Expected: `PDF written`.

- [ ] **Step 3: Inspect the PDF** — verify with pypdf:
- exactly 2 pages (or page 2 contains all 3 canvas charts — extract text with pypdf and confirm "12-Month Trend" text exists; charts themselves are canvas-rendered, check visually)
- Page 1: 3 month cards side by side (visually inspect — open the PDF for the user or describe expected layout), "Individual Performance" title WITHOUT "(Approved By)", avg values are whole numbers (e.g. 262).
- Page 2: all 3 charts stacked full-width.
- A4 page size: `pdf.page(0).mediabox` ≈ 595 x 842 pt.
Report what you found; ask the user to open `output/KPI_Report_Visual_Check.pdf` for a visual pass/fail.

- [ ] **Step 4: Full suite** — `..\..\.venv-win\Scripts\python.exe -m pytest tests -v` — Expected: all pass. No commits in this task.

---
## Self-Review Notes

- Spec coverage: cards row → Task 1.2; title → Task 1.3; charts page → Task 1.4; month-skip for performance → Task 2; ceil → Task 2; A4 → already set, verified Task 3 Step 3.
- Type consistency: `avg` becomes int in Task 2; renderer and template render it unchanged (Jinja prints `262` vs `262.0`); renderer's no-data gate reads `avg_per_day["bd"]["lines"]` — untouched. `performance` shape changes: `month_labels` may be `[]`; template's colspan fallback `{{ 1 + performance.month_labels|length }}` handles 0. No other consumers.

# KPI Report Iteration 2 (Visual Polish) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the redesigned KPI report PDF — two-page structure with repeating header/footer (TPS report pattern), decluttered page 1 with breathing room, and one combined BD/CN reflected-lines chart.

**Architecture:** Template-only changes in `templates/kpi_report.html.j2` plus its renderer test. The single `.page` div becomes two `.page` divs (each with its own page-header/page-footer), mirroring `templates/report.html.j2` and `templates/summary_report.html.j2`. The two reflected-lines Chart.js canvases merge into one chart with two datasets. No metrics/renderer/logic changes.

**Tech Stack:** Jinja2, CSS, Chart.js.

## Global Constraints

- Environment: Windows + PowerShell 5.1 (no bash). Python: `D:\Primark Report Generator\.venv-win\Scripts\python.exe` (absolute path). Work with workdir `D:\Primark Report Generator\tps-pipeline`.
- tps-pipeline is its own git repo (nested). Run git with workdir `D:\Primark Report Generator\tps-pipeline`. Use per-command identity: `git -c user.name=Shoaib -c user.email=shoaib@local commit -m "<message>"`. Stage ONLY the files named in the task. Do NOT stage or modify any other file (menu.py has unrelated uncommitted WIP — leave it alone).
- Design doc: `docs/superpowers/specs/2026-08-04-kpi-report-visual-redesign-design.md` (OUTER repo, commits 4a5a808 + 658ad50). Sections 7-9 are the binding requirements for this plan.
- Reference structure for per-page header/footer: `templates/report.html.j2` lines 775-1150 and `templates/summary_report.html.j2` lines 260-530 — each `<div class="page">` (second+ pages use `<div class="page page-break">`) contains its own page-header, page-content, and page-footer.
- Current template to edit: `templates/kpi_report.html.j2` (216 lines) — single `.page` div; charts wrapped in `<div class="charts-page">`; two region canvases `chartBdLines` and `chartCnLines`.

---
## Task 1: Two-page structure, repeated header/footer, declutter, combined region chart

**Files:**
- Modify: `templates/kpi_report.html.j2`
- Modify: `tests/test_kpi_renderer.py`

**Interfaces:**
- Consumes: unchanged context from `kpi_renderer.render_kpi_report` — `month_name`, `year`, `release_date`, `monthly_tables`, `performance`, `avg_per_day`, `trend`, `region_lines` (`{"labels", "bd", "cn"}`), `primark_logo`, `allport_logo`.
- Produces: HTML with exactly two `.page` divs, each containing `.page-header` (logos + red accent) and `.page-footer` ("Generated: {{ release_date }}" | "TPS KPI Report"); one combined region chart canvas `chartRegion` (chartBdLines/chartCnLines removed); decluttered page-1 spacing with guaranteed blank space below the avg blocks.

- [ ] **Step 1: Write the failing test** — replace the body of `tests/test_kpi_renderer.py::TestRenderKpiReport::test_renders_full_html` with:

```python
    def test_renders_full_html(self, mock_metrics):
        html = kpi_renderer.render_kpi_report(date(2026, 6, 1))
        assert "Transit Packaging System (TPS) KPI Report" in html
        assert "Individual Performance" in html
        assert "Individual Performance (Approved By)" not in html
        assert "Average Lines Processed Per Day" in html
        assert html.count("page-header") == 2
        assert html.count("page-footer") == 2
        assert "page-break" in html
        assert "month-cards" in html
        assert "chartTrend" in html
        assert "chartRegion" in html
        assert "chartBdLines" not in html
        assert "chartCnLines" not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `D:\Primark Report Generator\.venv-win\Scripts\python.exe -m pytest tests\test_kpi_renderer.py::TestRenderKpiReport::test_renders_full_html -v`
Expected: FAIL — `html.count("page-header") == 2` is 1, and `"chartRegion"` not found.

- [ ] **Step 3: Modify the template** — apply these edits to `templates/kpi_report.html.j2`:

**3a. CSS block (lines 10-45):** replace the two rules below, and add three new rules:

Replace line 11:
```css
    .page { width: 210mm; min-height: 297mm; background: white; margin: 0 auto 5px auto; display: flex; flex-direction: column; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
```
with:
```css
    .page { width: 210mm; min-height: 297mm; background: white; margin: 0 auto 5px auto; display: flex; flex-direction: column; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .page.page-break { page-break-before: always; }
```

Replace line 15:
```css
    .page-content { flex: 1; padding: 12px 18px; }
```
with:
```css
    .page-content { flex: 1; padding: 20px 26px; }
```

Replace line 20:
```css
    .section-header { display: flex; align-items: center; gap: 10px; margin: 12px 0 6px; }
```
with:
```css
    .section-header { display: flex; align-items: center; gap: 10px; margin: 20px 0 10px; }
```

Replace line 30:
```css
    .avg-blocks { display: flex; gap: 10px; margin-bottom: 10px; }
```
with:
```css
    .avg-blocks { display: flex; gap: 14px; margin-bottom: 10px; }
```

Replace line 35:
```css
    .month-cards { display: flex; gap: 10px; margin-bottom: 10px; }
```
with:
```css
    .month-cards { display: flex; gap: 14px; margin-bottom: 10px; }
```

Replace line 36:
```css
    .month-card { flex: 1; border: 1px solid #e5e7eb; border-radius: 10px; padding: 10px; background: #f9fafb; }
```
with:
```css
    .month-card { flex: 1; border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px; background: #f9fafb; }
```

Replace line 41:
```css
    .charts-page { page-break-before: always; }
```
with:
```css
    .page-bottom-space { flex: 1; min-height: 80px; }
```

Keep line 42-43 (`.chart-box` and canvas rules) unchanged.

**3b. Body structure (lines 47-168):** replace the whole `<div class="page">...</div>` block (lines 48-168) with two pages:

```html
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

    <div class="section-header">
      <span class="section-title">Individual Performance</span>
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

    <div class="page-bottom-space"></div>
  </div>

  <div class="page-footer">
    <span>Generated: {{ release_date }}</span>
    <span>TPS KPI Report</span>
  </div>
</div>

<div class="page page-break">
  <div class="page-header">
    <img class="brand-img-primark" src="{{ primark_logo }}" alt="Primark">
    <img class="brand-img-allport" src="{{ allport_logo }}" alt="Allport Pacd">
  </div>

  <div class="page-content">
    <div class="section-header">
      <span class="section-title">12-Month Trend</span>
      <div class="section-line"></div>
    </div>
    <div class="chart-box">
      <div class="chart-box-title">Suppliers & Factories (Last 12 Months)</div>
      <canvas id="chartTrend"></canvas>
    </div>
    <div class="chart-box">
      <div class="chart-box-title">Reflected Lines — BD & CN Regions</div>
      <canvas id="chartRegion"></canvas>
    </div>
  </div>

  <div class="page-footer">
    <span>Generated: {{ release_date }}</span>
    <span>TPS KPI Report</span>
  </div>
</div>
```

**3c. Chart.js script:** replace the two `new Chart(...)` blocks for `chartBdLines` (lines 196-203) and `chartCnLines` (lines 205-212) with ONE combined chart:

```js
  new Chart(document.getElementById('chartRegion'), {
    type: 'line',
    data: {
      labels: {{ region_lines.labels|tojson }},
      datasets: [
        { label: 'BD Region', data: {{ region_lines.bd }}, borderColor: '#059669', backgroundColor: 'transparent', tension: 0.4, fill: false },
        { label: 'CN Region', data: {{ region_lines.cn }}, borderColor: '#ea580c', backgroundColor: 'transparent', tension: 0.4, fill: false }
      ]
    },
    options: chartDefaults
  });
```

- [ ] **Step 4: Run test to verify it passes**

Run: `D:\Primark Report Generator\.venv-win\Scripts\python.exe -m pytest tests\test_kpi_renderer.py -v`
Expected: PASS (2 tests). Then full suite: `D:\Primark Report Generator\.venv-win\Scripts\python.exe -m pytest tests -v` — Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add templates/kpi_report.html.j2 tests/test_kpi_renderer.py
git -c user.name=Shoaib -c user.email=shoaib@local commit -m "feat: two-page kpi layout with repeated header/footer and combined region chart"
```

---
## Task 2: End-to-end verification

**Files:** none (no code changes, no commits).

**Interfaces:**
- Consumes: Task 1 template; `kpi_renderer.render_kpi_report` + `pdfgen.html_to_pdf`; PostgreSQL 16 (`C:\Program Files\PostgreSQL\16\bin\psql.exe`, db `tps_compliance`, user `postgres`, password `postgres`, `$env:PGPASSWORD = "postgres"`). raw_data currently has 98,984 rows.

- [ ] **Step 1: Regenerate the PDF** — from `tps-pipeline`:

```powershell
D:\Primark Report Generator\.venv-win\Scripts\python.exe -c "import sys; sys.path.insert(0, '.'); import os; os.chdir(r'D:\Primark Report Generator\tps-pipeline'); import kpi_renderer, pdfgen; from pathlib import Path; html = kpi_renderer.render_kpi_report(); out = r'D:\Primark Report Generator\tps-pipeline\output\KPI_Report_Visual_Check.pdf'; Path(out).unlink(missing_ok=True); print('PDF written' if pdfgen.html_to_pdf(html, out) else 'FAILED')"
```
Expected: `PDF written`.

- [ ] **Step 2: Inspect with pypdf** — verify:
- exactly 2 pages; A4: `page.mediabox` ≈ 595 x 842 pt on both pages.
- Text present on BOTH pages via `page.extract_text()`: "Generated:" (footer) on page 1 AND page 2; "TPS KPI Report" on both.
- Page 2 text contains "12-Month Trend".
- 2 canvases total across the PDF (chartTrend + chartRegion) — count XObject images per page (each chart renders as one image; page 2 should have 2 chart images + 2 logo images).
- Write these findings into your report.

- [ ] **Step 3: Full suite** — `D:\Primark Report Generator\.venv-win\Scripts\python.exe -m pytest tests -v` — Expected: all pass. No commits in this task.

- [ ] **Step 4: Report** — write your full report to `D:\Primark Report Generator\.superpowers\sdd\2026-08-04-kpi-report-visual-redesign-plan\task-2-report.md` (every command + output, PDF path, pypdf findings). If anything unexpected: do NOT modify code; record it, run the suite, report BLOCKED.

---
## Self-Review Notes

- Spec coverage: section 7 (two pages, repeated header/footer) → Task 1 3b/3a; section 8 (declutter + blank space) → Task 1 3a + `.page-bottom-space`; section 9 (combined chart) → Task 1 3b/3c. E2E → Task 2.
- Type consistency: `region_lines` shape unchanged; test asserts chartBdLines/chartCnLines absent; renderer test fixture unaffected.
- Placeholder scan: all code blocks are complete and verbatim.

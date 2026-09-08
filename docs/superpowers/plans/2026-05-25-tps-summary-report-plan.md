# TPS Compliance Report Summary - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new "[4] Summary Report" menu option that generates a single TPS Compliance Report Summary PDF containing aggregated data across all suppliers for a given month.

**Architecture:** Separate from the existing per-supplier report system. Uses a new `summary_renderer.py` (mirrors `renderer.py`), new `summary_report.html.j2` template, new `get_summary_*` metrics functions, and a new menu handler in `menu.py`.

**Tech Stack:** Python 3, SQLAlchemy, Jinja2, Playwright, Chart.js (CDN), pypdf

---

## File Structure

### New Files
- `tps-pipeline/summary_renderer.py` - renders summary report (mirrors `renderer.py` pattern)
- `tps-pipeline/templates/summary_report.html.j2` - HTML template for summary page
- `tests/test_summary_renderer.py` - unit tests for summary rendering

### Modified Files
- `tps-pipeline/metrics.py` - add 4 new `get_summary_*` functions
- `tps-pipeline/menu.py` - add option [4] and `handle_generate_summary_report()`
- `tps-pipeline/templates/report.css` - ensure consistent styling (already exists)

---

## Task 1: Add Summary Metrics Functions to metrics.py

**Files:**
- Modify: `tps-pipeline/metrics.py:600` (after existing functions)

### New Functions to Add

#### 1. `get_summary_sources(report_month: date) -> dict`
Returns: `{"total_suppliers": int, "total_factories": int}`

SQL query aggregates DISTINCT supplier and factory counts for the month.

#### 2. `get_summary_country_compliance(report_month: date) -> list[dict]`
Returns: `[{"country": str, "compliance_rate": float}, ...]` sorted by country

Compliance rate = (compliant rows / total rows) * 100 for each country.

#### 3. `get_summary_country_volume(report_month: date) -> list[dict]`
Returns: `[{"country": str, "carton_qty": int, "product_qty": int, "unit_cbm": float}, ...]`

- `carton_qty` = SUM(po_qty) for compliant rows per country
- `product_qty` = SUM(units_per_carton * po_qty) for compliant rows per country
- `unit_cbm` = AVG(density) for compliant rows per country

#### 4. `get_summary_country_monthly_trend(report_month: date) -> tuple[dict, list[str], list[str]]`
Returns: `(country_data, labels, supplier_order)`

- `country_data`: dict mapping country -> list of 12 monthly compliance rates
- `labels`: 12 month labels (e.g., "Jan '25", "Feb '25", ...)
- `supplier_order`: list of country names for chart legend

Uses same `_get_chart_month_range` logic as existing monthly compliance scores.

---

- [ ] **Step 1: Add get_summary_sources function**

```python
def get_summary_sources(report_month: date) -> dict:
    """Returns total unique suppliers and factories for the report month."""
    session = get_session()
    try:
        end = get_last_day_of_month(report_month)
        row = session.execute(text("""
            SELECT
                COUNT(DISTINCT supplier) AS total_suppliers,
                COUNT(DISTINCT factory) AS total_factories
            FROM raw_data
            WHERE handover_date >= :start AND handover_date < :end
        """), {"start": report_month, "end": end}).fetchone()
        return {
            "total_suppliers": row.total_suppliers if row else 0,
            "total_factories": row.total_factories if row else 0
        }
    finally:
        session.close()
```

- [ ] **Step 2: Add get_summary_country_compliance function**

```python
def get_summary_country_compliance(report_month: date) -> list[dict]:
    """Returns compliance rate per country for the report month."""
    session = get_session()
    try:
        end = get_last_day_of_month(report_month)
        rows = session.execute(text("""
            SELECT
                origin_country AS country,
                COUNT(*) FILTER (WHERE compliance_status = 'Compliant')::FLOAT / NULLIF(COUNT(*), 0) * 100 AS compliance_rate
            FROM raw_data
            WHERE handover_date >= :start AND handover_date < :end
              AND origin_country IS NOT NULL
            GROUP BY origin_country
            ORDER BY origin_country
        """), {"start": report_month, "end": end}).fetchall()
        return [
            {"country": row.country, "compliance_rate": round(row.compliance_rate, 1) if row.compliance_rate else 0.0}
            for row in rows
        ]
    finally:
        session.close()
```

- [ ] **Step 3: Add get_summary_country_volume function**

```python
def get_summary_country_volume(report_month: date) -> list[dict]:
    """Returns volume stats (carton qty, product qty, unit/cbm) per country for compliant rows."""
    session = get_session()
    try:
        end = get_last_day_of_month(report_month)
        rows = session.execute(text("""
            SELECT
                origin_country AS country,
                COALESCE(SUM(po_qty) FILTER (WHERE compliance_status = 'Compliant'), 0) AS carton_qty,
                COALESCE(SUM(units_per_carton * po_qty) FILTER (WHERE compliance_status = 'Compliant' AND units_per_carton IS NOT NULL), 0) AS product_qty,
                COALESCE(AVG(density) FILTER (WHERE compliance_status = 'Compliant' AND density IS NOT NULL), 0) AS unit_cbm
            FROM raw_data
            WHERE handover_date >= :start AND handover_date < :end
              AND origin_country IS NOT NULL
            GROUP BY origin_country
            ORDER BY origin_country
        """), {"start": report_month, "end": end}).fetchall()
        return [
            {
                "country": row.country,
                "carton_qty": int(row.carton_qty) if row.carton_qty else 0,
                "product_qty": int(row.product_qty) if row.product_qty else 0,
                "unit_cbm": round(row.unit_cbm, 1) if row.unit_cbm else 0.0
            }
            for row in rows
        ]
    finally:
        session.close()
```

- [ ] **Step 4: Add get_summary_country_monthly_trend function**

```python
def get_summary_country_monthly_trend(report_month: date) -> tuple[dict, list[str], list[str]]:
    """Returns (country_data, labels, country_order) for 12-month trend chart."""
    session = get_session()
    try:
        import calendar
        months_list = _get_chart_month_range_for_all(report_month)  # Same as _get_chart_month_range but without supplier filter
        
        if not months_list:
            return ({"No Data": [0.0]}, ["No Data"], ["No Data"])
        
        # Get all countries with data in the range
        all_countries_query = text("""
            SELECT DISTINCT origin_country
            FROM raw_data
            WHERE origin_country IS NOT NULL
            ORDER BY origin_country
        """)
        all_countries = [row[0] for row in session.execute(all_countries_query).fetchall()]
        
        labels = [f"{calendar.month_abbr[m.month]} '{str(m.year)[-2:]}" for m in months_list]
        country_data = {}
        
        for country in all_countries:
            country_data[country] = []
            for month_start in months_list:
                month_end = get_last_day_of_month(month_start)
                row = session.execute(text("""
                    SELECT
                        COUNT(*) FILTER (WHERE compliance_status = 'Compliant') AS compliant,
                        COUNT(*) AS total
                    FROM raw_data
                    WHERE origin_country = :country
                      AND handover_date >= :start AND handover_date < :end
                """), {"country": country, "start": month_start, "end": month_end}).fetchone()
                if row.total == 0:
                    score = 0.0
                else:
                    score = round(row.compliant / row.total * 100, 1)
                country_data[country].append(score)
        
        return (country_data, labels, all_countries)
    finally:
        session.close()


def _get_chart_month_range_for_all(report_month: date) -> list[date]:
    """Same as _get_chart_month_range but for all data (no supplier filter)."""
    min_date_query = text("SELECT MIN(handover_date) FROM raw_data")
    session = get_session()
    try:
        min_result = session.execute(min_date_query).fetchone()
        if min_result is None or min_result[0] is None:
            return [date(report_month.year, report_month.month, 1)]
        db_first = date(min_result[0].year, min_result[0].month, 1)
    finally:
        session.close()
    
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
```

- [ ] **Step 5: Run tests**

Run: `cd /home/shoaib/projects/Primark\ Report\ Generator/tps-pipeline && source .venv/bin/activate && python -m pytest tests/ -q`
Expected: All existing tests pass

- [ ] **Step 6: Commit**

```bash
git add tps-pipeline/metrics.py
git commit -m "feat: add summary report metrics functions"
```

---

## Task 2: Create Summary Report Template

**Files:**
- Create: `tps-pipeline/templates/summary_report.html.j2`

This template renders a single page: "TPS Compliance Report Summary for {Month Year}"

Contains:
1. Page header with logos
2. Sources table (Total Suppliers | Total Factories)
3. Compliance Score table (Country | Compliance Rate %)
4. Volume table (Country | Carton Qty | Product Qty | Unit/CBM)
5. Bar chart canvas with Chart.js showing 12-month trend by country

Reference styling from existing `report.html.j2` and `report.css`.

---

- [ ] **Step 1: Create summary_report.html.j2**

```jinja2
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      font-size: 12px;
      line-height: 1.4;
      color: #1a1a1a;
      background: #e5e7eb;
    }

    @page { size: A4 portrait; margin: 0; }

    .page {
      width: 210mm;
      height: 297mm;
      overflow: hidden;
      background: white;
      margin: 0 auto 10px auto;
      display: flex;
      flex-direction: column;
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    .page-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 16px;
      border-bottom: 4px solid #1B2838;
      background: white;
      flex-shrink: 0;
    }

    .brand-img-primark { height: 25px; width: auto; }
    .brand-img-allport { height: 28px; width: auto; }

    .page-content {
      flex: 1;
      padding: 16px 24px;
      display: flex;
      flex-direction: column;
    }

    .report-title {
      text-align: center;
      margin-bottom: 16px;
    }
    .report-title h1 {
      font-size: 22px;
      font-weight: 800;
      color: #1B2838;
    }
    .report-title h2 {
      font-size: 14px;
      font-weight: 600;
      color: #6B7280;
      text-transform: uppercase;
      letter-spacing: 1px;
    }

    .page-footer {
      display: flex;
      justify-content: space-between;
      padding: 6px 16px;
      border-top: 1px solid #E5E7EB;
      font-size: 8px;
      color: #6B7280;
    }

    table { width: 100%; border-collapse: collapse; margin-bottom: 14px; }
    th {
      background: #1B2838;
      color: white;
      font-weight: 600;
      text-transform: uppercase;
      font-size: 8px;
      padding: 6px 8px;
      text-align: left;
    }
    td { padding: 5px 8px; border-bottom: 1px solid #E5E7EB; font-size: 10px; }
    tr:nth-child(even) { background: #F9FAFB; }

    .table-title {
      font-size: 10px;
      font-weight: 700;
      color: #1B2838;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 6px;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
      margin-bottom: 16px;
    }

    .summary-section { }
  </style>
</head>
<body>
  <div class="page">
    <div class="page-header">
      <img class="brand-img-primark" src="{{ primark_logo }}" alt="Primark">
      <img class="brand-img-allport" src="{{ allport_logo }}" alt="Allport">
    </div>

    <div class="page-content">
      <div class="report-title">
        <h1>TPS Compliance Report</h1>
        <h2>Summary for {{ month_name }} {{ year }}</h2>
      </div>

      <div class="summary-grid">
        <div class="summary-section">
          <div class="table-title">Sources</div>
          <table>
            <thead>
              <tr>
                <th>Total Suppliers</th>
                <th>Total Factories</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>{{ sources.total_suppliers }}</td>
                <td>{{ sources.total_factories }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="summary-section">
          <div class="table-title">Compliance Score</div>
          <table>
            <thead>
              <tr>
                <th>Country</th>
                <th class="text-right">Compliance Rate (%)</th>
              </tr>
            </thead>
            <tbody>
              {% for c in compliance_data %}
              <tr>
                <td>{{ c.country }}</td>
                <td class="text-right">{{ c.compliance_rate }}%</td>
              </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>

      <div class="summary-section">
        <div class="table-title">Volume (Compliant Only)</div>
        <table>
          <thead>
            <tr>
              <th>Country</th>
              <th class="text-right">Carton Qty</th>
              <th class="text-right">Product Qty</th>
              <th class="text-right">Unit/CBM</th>
            </tr>
          </thead>
          <tbody>
            {% for v in volume_data %}
            <tr>
              <td>{{ v.country }}</td>
              <td class="text-right">{{ v.carton_qty }}</td>
              <td class="text-right">{{ v.product_qty }}</td>
              <td class="text-right">{{ v.unit_cbm }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>

      <div class="summary-section" style="flex: 1;">
        <div class="table-title">Trend Analysis</div>
        <div style="height: 100px; position: relative;">
          <canvas id="trendChart"></canvas>
        </div>
      </div>
    </div>

    <div class="page-footer">
      <span>Generated: {{ release_date }}</span>
      <span>TPS Summary Report</span>
    </div>
  </div>

  <script>
    const chartDefaults = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { boxWidth: 8, padding: 4, font: { size: 8 } } } },
      scales: {
        x: { ticks: { font: { size: 7 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
        y: { min: 0, max: 100, ticks: { stepSize: 25, font: { size: 8 } } }
      }
    };

    const chartColors = [
      '#1B2838', '#4A90D9', '#16a34a', '#ea580c', '#dc2626',
      '#7C3AED', '#DB2777', '#059669', '#F59E0B', '#6B7280'
    ];

    new Chart(document.getElementById('trendChart'), {
      type: 'bar',
      data: {
        labels: {{ chart_labels|tojson }},
        datasets: [
          {% for country in country_order %}
          {
            label: '{{ country }}',
            data: {{ country_data[country]|tojson }},
            backgroundColor: chartColors[{{ loop.index0 }} % chartColors.length],
            borderWidth: 0,
            borderRadius: 2
          },
          {% endfor %}
        ]
      },
      options: chartDefaults
    });
  </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add tps-pipeline/templates/summary_report.html.j2
git commit -m "feat: add summary report HTML template"
```

---

## Task 3: Create Summary Renderer

**Files:**
- Create: `tps-pipeline/summary_renderer.py`

Mirrors the pattern of `renderer.py` but returns a single HTML string (no portrait/landscape split).

---

- [ ] **Step 1: Create summary_renderer.py**

```python
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from datetime import date, datetime
import base64

from metrics import (
    get_report_month,
    get_summary_sources,
    get_summary_country_compliance,
    get_summary_country_volume,
    get_summary_country_monthly_trend
)

CONFIG_PATH = Path(__file__).parent / "config.yaml"
ASSETS_PATH = Path(__file__).parent / "assets"

def _load_logo(name: str) -> str:
    with open(ASSETS_PATH / name, "rb") as f:
        return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"

PRIMARK_LOGO = _load_logo("Primark-logo.png")
ALLPORT_LOGO = _load_logo("allport-pacd-logo.png")


def render_summary_report(report_month: date | None = None) -> str:
    if report_month is None:
        report_month = get_report_month()

    sources = get_summary_sources(report_month)
    compliance_data = get_summary_country_compliance(report_month)
    volume_data = get_summary_country_volume(report_month)
    country_data, chart_labels, country_order = get_summary_country_monthly_trend(report_month)

    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"])
    )
    template = env.get_template("summary_report.html.j2")

    context = {
        "month_name": report_month.strftime("%B"),
        "year": report_month.year,
        "release_date": datetime.now().strftime("%d %B %Y"),
        "sources": sources,
        "compliance_data": compliance_data,
        "volume_data": volume_data,
        "country_data": country_data,
        "chart_labels": chart_labels,
        "country_order": country_order,
        "primark_logo": PRIMARK_LOGO,
        "allport_logo": ALLPORT_LOGO,
    }

    return template.render(**context)
```

- [ ] **Step 2: Commit**

```bash
git add tps-pipeline/summary_renderer.py
git commit -m "feat: add summary report renderer"
```

---

## Task 4: Add Summary Report Menu Option

**Files:**
- Modify: `tps-pipeline/menu.py:20-30` (banner), `menu.py:163-176` (main loop)

---

- [ ] **Step 1: Update print_banner to add option [4]**

Change:
```
║   [1] Process New File                   ║
║   [2] Generate Reports                  ║
║   [3] View Logs                          ║
║   [0] Exit                               ║
```

To:
```
║   [1] Process New File                   ║
║   [2] Generate Reports                  ║
║   [3] Generate Summary Report           ║
║   [4] View Logs                          ║
║   [0] Exit                               ║
```

(Note: shuffle View Logs to [4], add Summary to [3])

Actually the user said option [2] keeps doing what it does. So add Summary as [3] and keep View Logs as [4]:
```
║   [1] Process New File                   ║
║   [2] Generate Reports                  ║
║   [3] Generate Summary Report           ║
║   [4] View Logs                          ║
║   [0] Exit                               ║
```

- [ ] **Step 2: Add handle_generate_summary_report function**

```python
def handle_generate_summary_report():
    config_path = Path(__file__).parent / "config.yaml"
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return
    output_dir = Path(__file__).parent / config["paths"]["output_dir"]
    output_dir.mkdir(exist_ok=True)

    print("\n=== Summary Report Month Selection ===")
    print("Enter year and month (or press Enter for default: previous month)")
    year_input = input("Year (e.g., 2026) [default: previous month]: ").strip()
    month_input = input("Month (1-12) [default: previous month]: ").strip()

    report_month = None
    if month_input:
        try:
            year = int(year_input) if year_input else (date.today().year)
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

    logger.info(f"Generating summary report for {report_month.strftime('%B %Y')}")
    print(f"Generating summary report for {report_month.strftime('%B %Y')}...")

    try:
        from summary_renderer import render_summary_report
        from pdfgen import html_to_pdf
        
        html_content = render_summary_report(report_month)
        file_date = report_month.strftime("%B_%Y")
        output_path = output_dir / f"TPS_Compliance_Summary_{file_date}.pdf"

        if output_path.exists():
            output_path.unlink()

        html_to_pdf(html_content, str(output_path))
        logger.info(f"Summary report saved: {output_path}")
        print(f"Summary report generated: {output_path}")
    except Exception as e:
        logger.error(f"Error generating summary report: {e}")
        print(f"Error: {e}")
```

- [ ] **Step 3: Update main() to handle choice "3"**

In the main while loop, add:
```python
elif choice == "3":
    handle_generate_summary_report()
```

- [ ] **Step 4: Run tests**

Run: `cd /home/shoaib/projects/Primark\ Report\ Generator/tps-pipeline && source .venv/bin/activate && python -m pytest tests/ -q`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add tps-pipeline/menu.py
git commit -m "feat: add menu option [3] for summary report"
```

---

## Self-Review Checklist

- [ ] All 4 new metrics functions implemented in metrics.py
- [ ] Summary template uses same CSS classes as existing report (consistent styling)
- [ ] Chart.js uses dataset-per-country pattern (multi-bar per month)
- [ ] Menu option [2] unchanged (still generates per-supplier reports)
- [ ] Menu option [3] generates summary report
- [ ] No changes to renderer.py or report.html.j2
- [ ] Tests pass

If all checks pass, the implementation is complete.
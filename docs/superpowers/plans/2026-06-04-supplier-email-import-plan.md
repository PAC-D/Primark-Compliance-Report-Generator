# Supplier Email Import Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import supplier emails from Excel into database, display in Suppliers Below Threshold sheet of Summary Report.

**Architecture:** New `supplier_emails` database table stores supplier-name/email pairs. On import, table is cleared then populated. During summary report generation, emails are looked up and aggregated per supplier for display.

**Tech Stack:** Python, SQLAlchemy, openpyxl, PostgreSQL

---

## File Structure

```
tps-pipeline/
├── database.py              # Modify: add init_supplier_emails_table()
├── menu.py                 # Modify: add handle_import_emails() + menu option 6
├── metrics.py              # Modify: add get_supplier_emails_map()
├── _suppliers_below.py     # Modify: lookup and display emails
└── tests/
    └── test_metrics.py     # Modify: add tests for get_supplier_emails_map()
```

---

## Task 1: Add `supplier_emails` table to database.py

**Files:**
- Modify: `tps-pipeline/database.py`

- [ ] **Step 1: Add `init_supplier_emails_table()` function**

Add this function after `init_db()`:

```python
def init_supplier_emails_table() -> None:
    """Creates the supplier_emails table if it doesn't exist."""
    with _engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS supplier_emails (
                id SERIAL PRIMARY KEY,
                supplier_name TEXT NOT NULL,
                email TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS supplier_emails_supplier_email_idx
            ON supplier_emails (supplier_name, email)
        """))
        conn.commit()


def clear_supplier_emails() -> None:
    """Clears all rows from the supplier_emails table."""
    with _engine.connect() as conn:
        conn.execute(text("DELETE FROM supplier_emails"))
        conn.commit()


def insert_supplier_email(supplier_name: str, email: str) -> None:
    """Inserts a single supplier/email pair. Supplier name is lowercased."""
    with _engine.connect() as conn:
        conn.execute(
            text("INSERT INTO supplier_emails (supplier_name, email) VALUES (:supplier, :email)"),
            {"supplier": supplier_name.strip().lower(), "email": email.strip()}
        )
        conn.commit()
```

- [ ] **Step 2: Call `init_supplier_emails_table()` from existing `init_db()` flow**

In `init_db()` function, after the `raw_data` table creation, add:
```python
init_supplier_emails_table()
```

Run: `python -c "from database import init_db, get_session; init_db(); print('OK')"`

Expected: Should complete without errors

- [ ] **Step 3: Commit**

```bash
git add tps-pipeline/database.py
git commit -m "feat: add supplier_emails table and helper functions"
```

---

## Task 2: Add email import handler to menu.py

**Files:**
- Modify: `tps-pipeline/menu.py`

- [ ] **Step 1: Add imports for openpyxl and email functions**

After existing imports, add:
```python
import openpyxl
from database import clear_supplier_emails, insert_supplier_email, init_supplier_emails_table
```

- [ ] **Step 2: Update print_banner() to add option 6**

Change from:
```python
║   [5] Extract Supplier Data               ║
║   [0] Exit                               ║
```

To:
```python
║   [5] Extract Supplier Data               ║
║   [6] Import Supplier Emails              ║
║   [0] Exit                               ║
```

- [ ] **Step 3: Add `handle_import_emails()` function**

Add after `handle_extract_supplier_data()`:

```python
def handle_import_emails():
    root = tk.Tk()
    root.withdraw()
    try:
        filepath = filedialog.askopenfilename(
            title="Select Supplier Emails Excel File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
    finally:
        root.destroy()

    if not filepath:
        return

    logger.info(f"Importing supplier emails from: {filepath}")

    try:
        wb = openpyxl.load_workbook(filepath)
        ws = wb.active

        header_row = [cell.value for cell in ws[1]]
        if len(header_row) < 2:
            print("Error: Excel must have at least 2 columns (Supplier Name, Email)")
            return

        supplier_col = None
        email_col = None
        for i, h in enumerate(header_row):
            h_lower = (h or "").strip().lower()
            if "supplier" in h_lower and "name" in h_lower:
                supplier_col = i + 1
            elif "email" in h_lower:
                email_col = i + 1

        if not supplier_col or not email_col:
            print("Error: Could not find 'Supplier Name' and 'Email' columns")
            return

        init_supplier_emails_table()
        clear_supplier_emails()

        count = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            supplier_name = row[supplier_col - 1]
            email = row[email_col - 1]
            if supplier_name and email:
                insert_supplier_email(str(supplier_name), str(email))
                count += 1

        logger.info(f"Imported {count} supplier emails")
        print(f"Successfully imported {count} supplier emails")

    except Exception as e:
        logger.error(f"Error importing supplier emails: {e}")
        print(f"Error importing supplier emails: {e}")
```

- [ ] **Step 4: Add case 6 to main menu handler in `main()`**

Change:
```python
elif choice == "5":
    handle_extract_supplier_data()
elif choice == "0":
```

To:
```python
elif choice == "5":
    handle_extract_supplier_data()
elif choice == "6":
    handle_import_emails()
elif choice == "0":
```

Run: `python -c "from menu import print_banner; print_banner()"` to verify no syntax errors

- [ ] **Step 5: Commit**

```bash
git add tps-pipeline/menu.py
git commit -m "feat: add menu option 6 for importing supplier emails"
```

---

## Task 3: Add `get_supplier_emails_map()` to metrics.py

**Files:**
- Modify: `tps-pipeline/metrics.py`

- [ ] **Step 1: Add `get_supplier_emails_map()` function**

Add after `get_suppliers_below_threshold()` (around line 977):

```python
def get_supplier_emails_map() -> dict[str, str]:
    """Returns dict mapping lowercase supplier name to comma-separated emails."""
    session = get_session()
    try:
        rows = session.execute(text("""
            SELECT supplier_name, email FROM supplier_emails ORDER BY supplier_name, email
        "")).fetchall()

        email_map = {}
        for row in rows:
            key = row.supplier_name
            if key not in email_map:
                email_map[key] = []
            email_map[key].append(row.email)

        return {k: ", ".join(v) for k, v in email_map.items()}
    finally:
        session.close()
```

Run: `python -c "from metrics import get_supplier_emails_map; print(get_supplier_emails_map())"`

Expected: `{}` (empty dict if no emails imported yet)

- [ ] **Step 2: Commit**

```bash
git add tps-pipeline/metrics.py
git commit -m "feat: add get_supplier_emails_map() function"
```

---

## Task 4: Wire email lookup into Suppliers Below Threshold sheet

**Files:**
- Modify: `tps-pipeline/_suppliers_below.py`
- Modify: `tps-pipeline/summary_excel_renderer.py`

- [ ] **Step 1: Update `_build_suppliers_below_threshold_sheet()` to accept and use email_map**

Change the function signature from:
```python
def _build_suppliers_below_threshold_sheet(wb, suppliers_below, month_name, year):
```

To:
```python
def _build_suppliers_below_threshold_sheet(wb, suppliers_below, month_name, year, email_map=None):
    if email_map is None:
        email_map = {}
```

- [ ] **Step 2: Look up email for each supplier when populating row**

In the loop that writes data rows (around line 67), change:
```python
ws.cell(row=row, column=9, value="")
```

To:
```python
email = email_map.get(supplier["supplier"].strip().lower(), "")
ws.cell(row=row, column=9, value=email)
```

- [ ] **Step 3: Update call in `render_summary_excel()` to pass email_map**

In `summary_excel_renderer.py`, after getting `suppliers_below`:

```python
email_map = get_supplier_emails_map()
_build_suppliers_below_threshold_sheet(wb, suppliers_below, month_name, year, email_map)
```

Change the existing call from:
```python
_build_suppliers_below_threshold_sheet(wb, suppliers_below, month_name, year)
```

To:
```python
_build_suppliers_below_threshold_sheet(wb, suppliers_below, month_name, year, email_map)
```

Also add import:
```python
from metrics import get_supplier_emails_map
```

Run: `python -c "from summary_excel_renderer import render_summary_excel; wb = render_summary_excel(); print('OK')"` (verify no errors)

- [ ] **Step 4: Commit**

```bash
git add tps-pipeline/_suppliers_below.py tps-pipeline/summary_excel_renderer.py
git commit -m "feat: wire email lookup into Suppliers Below Threshold sheet"
```

---

## Verification

1. Run `menu.py` and select option 6 to import emails
2. Select a test Excel file with supplier names and emails
3. Select option 3 to generate summary report
4. Open the output Excel file and check the "Suppliers Below Threshold" sheet
5. Verify emails are populated for suppliers that exist in both the threshold list and email import

---

## Spec Coverage Check

| Spec Requirement | Task |
|------------------|------|
| Import Excel with Supplier Name + Email columns | Task 2 |
| Clear table before import | Task 2 |
| Case-insensitive matching | Task 3 (lowercased in storage + lookup) |
| Multiple emails → comma-separated | Task 3 |
| Not found → blank | Task 4 |
| New menu option 6 | Task 2 |
| Email column in Suppliers Below Threshold | Task 4 |
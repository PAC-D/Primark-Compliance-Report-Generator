# Supplier Email Import Feature

## Overview
Add ability to import supplier emails from an Excel file into the database, and display them in the "Suppliers Below Threshold" sheet of the Summary Report.

## User Flow
1. User selects new menu option `[6] Import Supplier Emails`
2. File picker opens to select Excel file
3. Excel is parsed (columns: Supplier Name, Email; single sheet)
4. `supplier_emails` table is cleared, then populated with email data
5. Confirmation message shown with count of emails imported

## Database

### Table: `supplier_emails`
```sql
CREATE TABLE supplier_emails (
    id SERIAL PRIMARY KEY,
    supplier_name TEXT NOT NULL,
    email TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX supplier_emails_supplier_idx ON supplier_emails (supplier_name, email);
```

- `supplier_name` stored in lowercase for case-insensitive matching
- `email` stores single email address per row
- Table cleared before each import

### Email Aggregation
Multiple emails for the same supplier are stored as separate rows. When displaying in the report, they are aggregated into a comma-separated string (e.g., "a@x.com, b@y.com").

## Matching Logic
- Case-insensitive match on supplier name
- If no email found for a supplier → email cell left blank

## Menu Addition
New option `[6] Import Supplier Emails` added to main menu.

```
╔══════════════════════════════════════════╗
║   TPS Compliance Report Generator        ║
╠══════════════════════════════════════════╣
║   [1] Process New File                   ║
║   [2] Generate Reports                  ║
║   [3] Generate Summary Report           ║
║   [4] View Logs                          ║
║   [5] Extract Supplier Data               ║
║   [6] Import Supplier Emails              ║
║   [0] Exit                               ║
╚══════════════════════════════════════════╝
```

## Files to Modify
- `database.py` - add `init_supplier_emails_table()` function
- `menu.py` - add `handle_import_emails()` and menu option 6
- `metrics.py` - add `get_supplier_emails_map()` function
- `_suppliers_below.py` - lookup and display emails in email column

## Implementation Notes
- Use openpyxl to read Excel file
- Normalize supplier names to lowercase for storage and matching
- Email aggregation done in metrics.py before returning to sheet builder
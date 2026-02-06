# Quick Start: Data Storage & Next Steps

## ✅ What's Already Set Up

### 1. **Automatic Database Persistence**
All processed invoices are now automatically saved to:
```
data/invoices.db  (SQLite database)
```

### 2. **Data That's Stored**
Every time you process an invoice, the system saves:
- ✅ Invoice details (vendor, amount, date, etc.)
- ✅ Validation results
- ✅ Approval decisions
- ✅ Complete audit trail
- ✅ Processing timestamps

### 3. **Available Export Formats**
- **JSON**: Machine-readable format
- **CSV**: Excel-compatible spreadsheet

## 🚀 How to Use It

### View Your Data

#### Via API
```bash
# Get all invoices
curl http://localhost:8000/api/database/invoices

# Get specific invoice
curl http://localhost:8000/api/database/invoice/abc123

# Get statistics
curl http://localhost:8000/api/database/statistics

# Get pending approvals
curl http://localhost:8000/api/approvals/pending
```

#### Via Export
```bash
# Export to JSON
curl http://localhost:8000/api/export/json

# Export approved invoices only
curl "http://localhost:8000/api/export/json?status=approved"

# Export to CSV
curl http://localhost:8000/api/export/csv
```

### Query Database Directly

Using SQLite command line or [DB Browser for SQLite](https://sqlitebrowser.org/):

```sql
-- View all invoices
SELECT * FROM invoices;

-- Get approved invoices
SELECT * FROM invoices WHERE status = 'approved';

-- Total invoices by vendor
SELECT vendor_name, COUNT(*), SUM(total_amount)
FROM invoices
GROUP BY vendor_name;

-- Pending approvals
SELECT invoice_id, vendor_name, total_amount, created_at
FROM invoices
WHERE status = 'pending_approval';
```

## 📊 What To Do With The Data

### Option 1: Manual Export for Accounting

1. **Export approved invoices**:
   ```
   GET /api/export/csv?status=approved
   ```

2. **Open in Excel**:
   - File saved to: `data/exports/invoices_YYYYMMDD_HHMMSS.csv`
   - Import into Excel/Google Sheets
   - Review and process

3. **Manual entry to accounting system**

### Option 2: Automated ERP Integration

#### SAP
```python
# See DATA_STORAGE_GUIDE.md - Section: SAP Integration
from src.integrations.sap_integration import sync_to_sap

# Run periodically (e.g., every hour)
sync_to_sap()
```

#### QuickBooks Online
```python
from src.integrations.quickbooks_integration import sync_approved_invoices_to_qbo

sync_approved_invoices_to_qbo()
```

#### NetSuite
```python
from src.integrations.netsuite_integration import create_vendor_bill
from src.database.invoice_db import get_database

db = get_database()
approved = db.get_approved_invoices()

for invoice in approved:
    create_vendor_bill(invoice)
```

### Option 3: Webhook Integration

Real-time push to external systems when invoices are approved:

```python
# In src/agents/invoice_agent.py (already integrated)
# Automatically sends webhook when status changes
```

Set your webhook URL in environment:
```bash
export WEBHOOK_URL="https://your-erp.com/webhooks/invoice"
```

## 📁 File Structure

```
data/
├── invoices.db          # SQLite database (all invoice data)
├── uploads/             # Uploaded invoice files (PDFs/images)
└── exports/             # Exported JSON/CSV files
    ├── invoices_YYYYMMDD_HHMMSS.json
    └── invoices_YYYYMMDD_HHMMSS.csv
```

## 🔄 Typical Workflow

```
1. Upload Invoice
   ↓
2. Auto-Extract Data
   ↓
3. Auto-Validate
   ↓
4. Route for Approval
   ↓
5. ✅ SAVED TO DATABASE ← You are here!
   ↓
6. [Choose your path]
   │
   ├→ A. Export to CSV → Manual entry to ERP
   ├→ B. API Integration → Auto-push to SAP/QuickBooks
   ├→ C. Webhook → Real-time notification to ERP
   └→ D. Query Database → Custom reporting
```

## 💡 Recommended Next Steps

### Immediate (No Coding Required)

1. **View your data**:
   ```bash
   # Download DB Browser for SQLite
   # Open: data/invoices.db
   # Browse tables: invoices, approvals, validations
   ```

2. **Export for review**:
   ```
   Visit: http://localhost:8000/api/export/csv
   Open CSV in Excel
   ```

3. **Check pending approvals**:
   ```
   Visit: http://localhost:8000/approvals
   Review and approve invoices
   ```

### Short-term (Minimal Coding)

1. **Schedule periodic export**:
   ```python
   # Create daily_export.py
   from src.database.invoice_db import get_database
   from datetime import datetime

   db = get_database()
   today = datetime.now().strftime('%Y%m%d')
   db.export_to_csv(f'exports/daily_{today}.csv', status='approved')
   ```

   Run daily via cron/Task Scheduler

2. **Email exports to accounting**:
   ```python
   import smtplib
   from email.mime.multipart import MIMEMultipart
   from email.mime.base import MIMEBase
   from email import encoders

   def email_approved_invoices():
       db = get_database()
       csv_file = db.export_to_csv('temp.csv', status='approved')

       msg = MIMEMultipart()
       msg['Subject'] = 'Daily Approved Invoices'
       msg['To'] = 'accounting@company.com'

       # Attach CSV
       with open(csv_file, 'rb') as f:
           part = MIMEBase('application', 'octet-stream')
           part.set_payload(f.read())
       encoders.encode_base64(part)
       part.add_header('Content-Disposition', f'attachment; filename="invoices.csv"')
       msg.attach(part)

       # Send email
       smtp = smtplib.SMTP('smtp.gmail.com', 587)
       smtp.starttls()
       smtp.login('your@email.com', 'password')
       smtp.send_message(msg)
   ```

### Long-term (Production Integration)

1. **ERP Integration** (See `DATA_STORAGE_GUIDE.md`):
   - SAP connector
   - QuickBooks API
   - NetSuite integration
   - Dynamics 365

2. **Migrate to PostgreSQL** (for scalability):
   ```python
   # Update connection string in invoice_db.py
   DATABASE_URL = "postgresql://user:pass@localhost/invoices"
   ```

3. **Add reporting dashboard**:
   - Power BI connection
   - Tableau integration
   - Custom analytics

## 🔍 Data Examples

### Invoice Data Structure
```json
{
  "invoice_id": "abc123",
  "vendor_name": "Anthropic, PBC",
  "invoice_number": "QQP4SA6U-0003",
  "invoice_date": "2026-01-13",
  "total_amount": 20.0,
  "currency": "USD",
  "status": "approved",
  "approval": {
    "approver_name": "Jane Doe",
    "action": "approve",
    "timestamp": "2026-02-05T11:00:00"
  }
}
```

## 📚 Documentation

- **Full Guide**: `DATA_STORAGE_GUIDE.md` (ERP integrations, webhooks)
- **Approval Guide**: `APPROVAL_GUIDE.md` (manual review process)
- **Database Schema**: See tables in `src/database/invoice_db.py`

## ✨ Key Takeaways

1. ✅ **Data is automatically saved** - no extra steps needed
2. ✅ **Multiple export formats** - JSON, CSV
3. ✅ **Query anytime** - API or direct database access
4. ✅ **ERP ready** - integration examples provided
5. ✅ **Audit trail** - complete history of all actions

**Your data is persistent and ready to use!** 🎉

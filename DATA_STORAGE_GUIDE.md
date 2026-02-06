# Data Storage & Integration Guide

## Current State: In-Memory Storage ⚠️

### Where Data Lives Now

**Location:** `invoice_agent.processing_history` (Python list in memory)

```python
# In src/agents/invoice_agent.py line 70
self.processing_history: list = []
```

**What This Means:**
- ✅ Fast access during runtime
- ❌ Data is LOST when application restarts
- ❌ No permanent record
- ❌ Cannot query historical data
- ❌ Not suitable for production

### Current Data Structure

Each processed invoice creates this record:
```json
{
  "invoice_id": "abc123",
  "document_path": "data/uploads/file.pdf",
  "timestamp": "2026-02-05T10:00:00",
  "result": {
    "invoice_id": "abc123",
    "success": true,
    "status": "approved",
    "invoice_data": {
      "vendor_name": "Anthropic, PBC",
      "invoice_number": "QQP4SA6U-0003",
      "invoice_date": "2026-01-13",
      "total_amount": 20.0,
      "currency": "USD",
      "subtotal": 20.0,
      "tax_amount": 0.0
    },
    "validation": {
      "overall_status": "passed",
      "validation_results": [...],
      "exceptions": []
    },
    "approval": {
      "approval_level": "manager",
      "assigned_to": "John Smith",
      "status": "approved",
      "reason": "Manual review required"
    },
    "approval_decision": {
      "action": "approve",
      "approver_name": "Jane Doe",
      "approver_email": "jane@company.com",
      "comments": "Approved",
      "timestamp": "2026-02-05T11:00:00"
    },
    "processing_time_ms": 25,
    "agent_actions": [...],
    "errors": []
  }
}
```

## Solution 1: Database Persistence (Recommended)

### SQLite Database (Simple, Local)

I'll create a database module for you:

**File:** `src/database/invoice_db.py` ✅ CREATED

### Database Tables

**invoices** - Main invoice data
```sql
- invoice_id (PRIMARY KEY)
- document_path
- vendor_name, invoice_number, invoice_date
- total_amount, currency, subtotal, tax_amount
- status, processing_time_ms
- created_at, updated_at
```

**validations** - Validation results
```sql
- invoice_id (FOREIGN KEY)
- overall_status
- can_auto_process
- validation_data (JSON)
```

**approvals** - Approval history
```sql
- invoice_id (FOREIGN KEY)
- approval_level, assigned_to, priority
- action (approve/reject)
- approver_name, approver_email, comments
- decision_at
```

**processing_history** - Complete audit trail
```sql
- invoice_id (FOREIGN KEY)
- success
- full_result (JSON)
- errors
- created_at
```

### Usage

#### Automatic (Integrated)

Database is now **automatically enabled** when you process invoices:

```python
# Database is initialized by default
agent = create_invoice_agent()

# Process invoice - automatically saves to database
result = await agent.process_invoice("invoice.pdf")

# Data is now persisted in: data/invoices.db
```

#### Manual Database Operations

```python
from src.database.invoice_db import get_database

db = get_database()

# Query invoices
all_invoices = db.get_all_invoices(limit=100)
pending = db.get_pending_approvals()
approved = db.get_approved_invoices()

# Get specific invoice
invoice = db.get_invoice("abc123")

# Update status
db.update_invoice_status("abc123", "approved")

# Get statistics
stats = db.get_statistics()
# Returns: {total_invoices, by_status, total_amount, avg_time}

# Export data
db.export_to_json("exports/invoices.json")
db.export_to_csv("exports/invoices.csv")
```

## Solution 2: Export Functionality

### API Endpoints

#### Export to JSON
```http
GET /api/export/json?status=approved
```

Response:
```json
{
  "success": true,
  "file_path": "data/exports/invoices_20260205_120000.json",
  "invoice_count": 50,
  "message": "Exported 50 invoices"
}
```

#### Export to CSV
```http
GET /api/export/csv?status=approved
```

#### Query Database
```http
GET /api/database/invoices?limit=100&status=approved
GET /api/database/invoice/abc123
GET /api/database/statistics
```

### Export Formats

**JSON Format:**
```json
[
  {
    "invoice_id": "abc123",
    "vendor_name": "Anthropic, PBC",
    "invoice_number": "QQP4SA6U-0003",
    "invoice_date": "2026-01-13",
    "total_amount": 20.0,
    "currency": "USD",
    "status": "approved",
    "created_at": "2026-02-05T10:00:00"
  }
]
```

**CSV Format:**
```csv
invoice_id,vendor_name,invoice_number,invoice_date,total_amount,currency,status
abc123,Anthropic PBC,QQP4SA6U-0003,2026-01-13,20.0,USD,approved
```

## Solution 3: ERP System Integration

### Common ERP Systems

#### 1. **SAP Integration**

```python
# src/integrations/sap_integration.py
from src.database.invoice_db import get_database

def sync_to_sap():
    """Sync approved invoices to SAP."""
    db = get_database()
    approved = db.get_approved_invoices()

    for invoice in approved:
        # Map to SAP format
        sap_payload = {
            "CompanyCode": "1000",
            "FiscalYear": invoice["invoice_date"][:4],
            "VendorCode": lookup_vendor_code(invoice["vendor_name"]),
            "InvoiceNumber": invoice["invoice_number"],
            "InvoiceDate": invoice["invoice_date"],
            "Amount": invoice["total_amount"],
            "Currency": invoice["currency"],
            "PONumber": invoice["po_number"]
        }

        # Post to SAP
        response = post_to_sap_api(sap_payload)

        if response["success"]:
            db.update_invoice_status(
                invoice["invoice_id"],
                "posted_to_sap"
            )
```

#### 2. **Oracle NetSuite Integration**

```python
# src/integrations/netsuite_integration.py
import requests

def create_vendor_bill(invoice_data: dict):
    """Create vendor bill in NetSuite."""

    netsuite_payload = {
        "subsidiary": "1",
        "vendor": {
            "internalId": get_vendor_id(invoice_data["vendor_name"])
        },
        "tranDate": invoice_data["invoice_date"],
        "dueDate": invoice_data["due_date"],
        "tranId": invoice_data["invoice_number"],
        "memo": f"Auto-created from Invoice {invoice_data['invoice_id']}",
        "itemList": {
            "item": [{
                "item": {"internalId": "1"},  # Expense account
                "amount": invoice_data["total_amount"],
                "description": f"Invoice {invoice_data['invoice_number']}"
            }]
        }
    }

    # Call NetSuite REST API
    response = requests.post(
        "https://yourcompany.suitetalk.api.netsuite.com/services/rest/record/v1/vendorBill",
        headers={
            "Authorization": f"Bearer {NETSUITE_TOKEN}",
            "Content-Type": "application/json"
        },
        json=netsuite_payload
    )

    return response.json()
```

#### 3. **QuickBooks Online Integration**

```python
# src/integrations/quickbooks_integration.py
from quickbooks import QuickBooks
from quickbooks.objects.bill import Bill

def sync_approved_invoices_to_qbo():
    """Sync approved invoices to QuickBooks Online."""
    db = get_database()
    qb = QuickBooks(
        client_id=QB_CLIENT_ID,
        client_secret=QB_CLIENT_SECRET,
        access_token=QB_ACCESS_TOKEN,
        company_id=QB_COMPANY_ID
    )

    approved = db.get_approved_invoices()

    for invoice_data in approved:
        bill = Bill()
        bill.VendorRef = get_qb_vendor_ref(invoice_data["vendor_name"])
        bill.TxnDate = invoice_data["invoice_date"]
        bill.DueDate = invoice_data["due_date"]
        bill.DocNumber = invoice_data["invoice_number"]
        bill.TotalAmt = invoice_data["total_amount"]

        bill.save(qb=qb)

        db.update_invoice_status(
            invoice_data["invoice_id"],
            "posted_to_quickbooks"
        )
```

#### 4. **Microsoft Dynamics 365 Integration**

```python
# src/integrations/dynamics_integration.py
import requests

def post_to_dynamics(invoice_data: dict):
    """Post invoice to Dynamics 365."""

    dynamics_url = "https://yourorg.api.crm.dynamics.com/api/data/v9.2"

    payload = {
        "name": invoice_data["invoice_number"],
        "msdyn_vendorinvoicenumber": invoice_data["invoice_number"],
        "msdyn_invoicedate": invoice_data["invoice_date"],
        "msdyn_totalamount": invoice_data["total_amount"],
        "transactioncurrencyid@odata.bind": f"/transactioncurrencies({get_currency_id(invoice_data['currency'])})",
        "msdyn_vendor@odata.bind": f"/accounts({get_vendor_id(invoice_data['vendor_name'])})"
    }

    response = requests.post(
        f"{dynamics_url}/msdyn_vendorinvoices",
        headers={
            "Authorization": f"Bearer {DYNAMICS_TOKEN}",
            "Content-Type": "application/json",
            "OData-MaxVersion": "4.0"
        },
        json=payload
    )

    return response.json()
```

## Solution 4: Webhook/API Integration

### Real-time Push to External Systems

```python
# src/integrations/webhooks.py
import requests
from typing import Dict, Any

class WebhookIntegration:
    """Push invoice data to external systems via webhook."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_invoice_approved(self, invoice_data: Dict[str, Any]):
        """Send webhook when invoice is approved."""

        payload = {
            "event": "invoice.approved",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "invoice_id": invoice_data["invoice_id"],
                "vendor_name": invoice_data["invoice_data"]["vendor_name"],
                "invoice_number": invoice_data["invoice_data"]["invoice_number"],
                "amount": invoice_data["invoice_data"]["total_amount"],
                "currency": invoice_data["invoice_data"]["currency"],
                "approval": invoice_data["approval_decision"]
            }
        }

        response = requests.post(
            self.webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        return response.status_code == 200


# Usage in invoice_agent.py
webhook = WebhookIntegration("https://your-erp.com/webhooks/invoice-approved")

# After approval
if result["status"] == "approved":
    webhook.send_invoice_approved(result)
```

## What to Do After Extraction & Approval

### Recommended Workflow

```
┌─────────────────────┐
│  Invoice Uploaded   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Extraction + AI     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Validation       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Routing/Approval   │
└──────────┬──────────┘
           │
           ▼
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌────────┐   ┌────────────┐
│ Auto   │   │  Manual    │
│Approve │   │  Review    │
└───┬────┘   └─────┬──────┘
    │              │
    └──────┬───────┘
           │
           ▼
┌─────────────────────┐
│  SAVE TO DATABASE   │ ◄── YOU ARE HERE
└──────────┬──────────┘
           │
     ┌─────┴─────────────────┐
     │                       │
     ▼                       ▼
┌──────────────┐      ┌──────────────┐
│ Export Data  │      │Push to ERP   │
│ (JSON/CSV)   │      │(SAP/QBO/etc) │
└──────────────┘      └──────────────┘
           │                  │
           └─────────┬────────┘
                     │
                     ▼
           ┌──────────────────┐
           │  Payment Queue   │
           └──────────────────┘
```

### Step-by-Step Actions

1. **✅ Extraction & Approval Complete**
   - Invoice data extracted
   - Validation passed
   - Approval granted

2. **💾 Save to Database** (Automatic)
   - Persisted in SQLite: `data/invoices.db`
   - Full audit trail maintained
   - Query anytime

3. **📤 Export Options**
   - **JSON**: For custom integrations
   - **CSV**: For Excel/reporting
   - **API**: Real-time access

4. **🔗 ERP Integration**
   - **SAP**: Create vendor invoice
   - **QuickBooks**: Create bill
   - **NetSuite**: Create vendor bill
   - **Dynamics**: Post to AP module

5. **💰 Payment Processing**
   - Export to payment system
   - Trigger ACH/Wire payment
   - Update payment status

## Testing the Database

```bash
# Process an invoice
curl -X POST http://localhost:8000/api/process \
  -F "file=@invoice.pdf"

# Check database
curl http://localhost:8000/api/database/invoices

# Get statistics
curl http://localhost:8000/api/database/statistics

# Export to JSON
curl http://localhost:8000/api/export/json

# Export approved invoices
curl "http://localhost:8000/api/export/json?status=approved"
```

## Database Location

Your invoice data is stored in:
```
data/invoices.db  (SQLite database)
```

You can:
- ✅ Open with SQLite Browser
- ✅ Query with SQL
- ✅ Backup easily (copy file)
- ✅ Migrate to PostgreSQL/MySQL later

## Next Steps

1. **Enable Database** (Already done automatically!)
2. **Process Invoices** - Data saved automatically
3. **Query Data** - Use API endpoints
4. **Export** - Generate reports
5. **Integrate ERP** - Connect to your accounting system
6. **Setup Webhooks** - Real-time notifications
7. **Schedule Sync** - Periodic data push to ERP

## Migration to Production Database

When ready for production, migrate from SQLite to PostgreSQL:

```python
# Update database connection in invoice_db.py
from sqlalchemy import create_engine

engine = create_engine('postgresql://user:pass@localhost/invoices')
```

All the same code will work with PostgreSQL!

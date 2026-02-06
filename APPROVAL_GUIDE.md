# Manual Approval Guide

## Overview

When an invoice requires manual review, it enters a **PENDING_APPROVAL** status. This guide explains how approvers can review and process these invoices.

## Approval Dashboard

### Accessing the Dashboard

1. Open your browser and navigate to: **http://localhost:8000/approvals**
2. The dashboard shows all invoices currently pending approval

### Dashboard Features

- **Real-time updates**: Auto-refreshes every 30 seconds
- **Invoice summary**: Shows key details (vendor, amount, priority, approval level)
- **Review button**: Opens detailed view for each invoice

## Approval Process

### Step 1: View Pending Approvals

The dashboard displays all invoices awaiting approval with:
- Vendor name
- Invoice number
- Total amount
- Invoice date
- Priority level (normal, high, critical)
- Required approval level (manager, director, executive, exception)

### Step 2: Review Invoice Details

Click the **Review** button to see full details:

**Invoice Details:**
- Invoice ID
- Invoice number
- Vendor name
- Total amount
- Invoice date
- Currency

**Approval Requirements:**
- Approval level (who needs to approve)
- Assigned approver
- Priority level
- Reason for this approval level

**Validation Status:**
- Overall validation status (passed/failed/warning)
- Specific validation checks performed

### Step 3: Make Decision

In the review modal, provide:
1. **Your Name** (required)
2. **Your Email** (required)
3. **Comments** (optional) - Add notes about your decision

Then click one of:
- **Approve** - Approve the invoice for payment
- **Reject** - Reject the invoice
- **Cancel** - Close without action

### Step 4: Confirmation

After submitting, you'll see:
- Success message
- Updated invoice status
- The invoice is removed from pending list

## Approval Levels

### Auto-Approved
- Amount ≤ $5,000
- All validations passed
- PO matched (if required)
- Vendor pre-approved
- **No manual review needed**

### Manager Review
- Amount: $5,001 - $25,000
- Assigned to: Department Manager
- SLA: 24-48 hours

### Director Review
- Amount: $25,001 - $100,000
- Assigned to: Director
- SLA: 24 hours

### Executive Review
- Amount: > $100,000
- Assigned to: Executive
- SLA: 4-8 hours

### Exception Handling
- Validation failures
- Missing PO
- Unapproved vendor
- Duplicate suspected
- Data quality issues

## API Endpoints

### Get Pending Approvals
```http
GET /api/approvals/pending
```

**Response:**
```json
{
  "pending_approvals": [
    {
      "invoice_id": "abc123",
      "timestamp": "2026-02-05T10:00:00",
      "invoice_data": {...},
      "validation": {...},
      "approval": {...}
    }
  ],
  "count": 1
}
```

### Submit Approval Decision
```http
POST /api/approvals/action
Content-Type: application/json

{
  "invoice_id": "abc123",
  "action": "approve",
  "approver_name": "John Doe",
  "approver_email": "john@company.com",
  "comments": "Approved as per budget"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Invoice abc123 approved by John Doe",
  "invoice_id": "abc123",
  "new_status": "approved"
}
```

## Workflow Diagram

```
┌─────────────────┐
│ Invoice Upload  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Extraction    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Validation    │
└────────┬────────┘
         │
         ▼
    ┌────┴────┐
    │ Routing │
    └────┬────┘
         │
    ┌────┴─────────────┐
    │                  │
    ▼                  ▼
┌────────┐      ┌──────────────┐
│  Auto  │      │   Manual     │
│Approve │      │   Review     │◄─── YOU ARE HERE
└────────┘      └──────┬───────┘
                       │
                  ┌────┴────┐
                  │         │
                  ▼         ▼
            ┌─────────┐ ┌────────┐
            │ Approve │ │ Reject │
            └────┬────┘ └───┬────┘
                 │          │
                 ▼          ▼
            ┌─────────────────┐
            │  Status Update  │
            └─────────────────┘
```

## Best Practices

### For Approvers

1. **Review Thoroughly**: Check all invoice details before approving
2. **Verify Amounts**: Ensure amounts match expectations
3. **Check Validation**: Review validation status and any warnings
4. **Add Comments**: Document your decision rationale
5. **Act Promptly**: Meet SLA deadlines to avoid delays

### For Administrators

1. **Monitor Dashboard**: Regularly check for pending approvals
2. **Escalate Issues**: Route exceptions to appropriate teams
3. **Track Metrics**: Monitor approval rates and processing times
4. **Audit Trail**: All approval actions are logged with timestamp and approver

## Troubleshooting

### Invoice Not Showing
- Check if invoice status is actually "pending_approval"
- Refresh the dashboard (auto-refreshes every 30 seconds)
- Verify invoice was processed successfully

### Cannot Submit Decision
- Ensure Name and Email are provided
- Check browser console for errors
- Verify network connection

### Wrong Approval Level
- Review business rules in configuration
- Check amount thresholds
- Validate vendor approval status

## Security Notes

- All actions are logged with approver information
- Approval decisions cannot be modified once submitted
- Audit trail includes timestamps and IP addresses (future enhancement)
- Role-based access control can be added for different approval levels

## Next Steps

After approval:
1. **Approved invoices** → Ready for payment processing
2. **Rejected invoices** → Returned to vendor or requester
3. **Metrics updated** → Dashboard shows updated statistics

## Support

For issues or questions:
- Check console logs in browser developer tools
- Review API endpoint responses
- Contact system administrator

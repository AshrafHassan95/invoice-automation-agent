"""
Database module for persisting invoice data.

Provides SQLite-based storage for:
- Processed invoices
- Approval history
- Audit trail
"""
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager


class InvoiceDatabase:
    """SQLite database for invoice persistence."""

    def __init__(self, db_path: str = "data/invoices.db"):
        """Initialize database connection."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()

    @contextmanager
    def get_connection(self):
        """Get database connection with automatic commit/rollback."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _create_tables(self):
        """Create database tables if they don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Main invoices table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    invoice_id TEXT PRIMARY KEY,
                    document_path TEXT,
                    vendor_name TEXT,
                    invoice_number TEXT,
                    invoice_date TEXT,
                    due_date TEXT,
                    total_amount REAL,
                    currency TEXT,
                    subtotal REAL,
                    tax_amount REAL,
                    po_number TEXT,
                    status TEXT,
                    processing_time_ms INTEGER,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

            # Validation results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS validations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id TEXT,
                    overall_status TEXT,
                    can_auto_process BOOLEAN,
                    validation_data TEXT,
                    created_at TEXT,
                    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
                )
            """)

            # Approval history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS approvals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id TEXT,
                    approval_level TEXT,
                    assigned_to TEXT,
                    priority TEXT,
                    reason TEXT,
                    action TEXT,
                    approver_name TEXT,
                    approver_email TEXT,
                    comments TEXT,
                    decision_at TEXT,
                    created_at TEXT,
                    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
                )
            """)

            # Processing history table (full record)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id TEXT,
                    success BOOLEAN,
                    full_result TEXT,
                    errors TEXT,
                    created_at TEXT,
                    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoice_status ON invoices(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoice_date ON invoices(invoice_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vendor ON invoices(vendor_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_approval_status ON approvals(action)")

    def save_invoice(self, result: Dict[str, Any]) -> bool:
        """
        Save processed invoice to database.

        Args:
            result: Processing result dictionary

        Returns:
            True if saved successfully
        """
        try:
            invoice_id = result.get("invoice_id")
            invoice_data = result.get("invoice_data", {})
            validation = result.get("validation", {})
            approval = result.get("approval", {})
            approval_decision = result.get("approval_decision", {})

            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Insert/Update invoice
                cursor.execute("""
                    INSERT OR REPLACE INTO invoices (
                        invoice_id, document_path, vendor_name, invoice_number,
                        invoice_date, due_date, total_amount, currency,
                        subtotal, tax_amount, po_number, status,
                        processing_time_ms, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    invoice_id,
                    result.get("document_path"),
                    invoice_data.get("vendor_name"),
                    invoice_data.get("invoice_number"),
                    invoice_data.get("invoice_date"),
                    invoice_data.get("due_date"),
                    invoice_data.get("total_amount"),
                    invoice_data.get("currency"),
                    invoice_data.get("subtotal"),
                    invoice_data.get("tax_amount"),
                    invoice_data.get("po_number"),
                    result.get("status"),
                    result.get("processing_time_ms"),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))

                # Insert validation
                if validation:
                    cursor.execute("""
                        INSERT INTO validations (
                            invoice_id, overall_status, can_auto_process,
                            validation_data, created_at
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        invoice_id,
                        validation.get("overall_status"),
                        validation.get("can_auto_process", False),
                        json.dumps(validation, default=str),
                        datetime.now().isoformat()
                    ))

                # Insert approval
                if approval:
                    cursor.execute("""
                        INSERT INTO approvals (
                            invoice_id, approval_level, assigned_to, priority,
                            reason, action, approver_name, approver_email,
                            comments, decision_at, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        invoice_id,
                        approval.get("approval_level"),
                        approval.get("assigned_to"),
                        approval.get("priority"),
                        approval.get("reason"),
                        approval_decision.get("action"),
                        approval_decision.get("approver_name"),
                        approval_decision.get("approver_email"),
                        approval_decision.get("comments"),
                        approval_decision.get("timestamp"),
                        datetime.now().isoformat()
                    ))

                # Insert full processing history
                cursor.execute("""
                    INSERT INTO processing_history (
                        invoice_id, success, full_result, errors, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    invoice_id,
                    result.get("success", False),
                    json.dumps(result, default=str),
                    json.dumps(result.get("errors", []), default=str),
                    datetime.now().isoformat()
                ))

            return True

        except Exception as e:
            print(f"Error saving invoice to database: {e}")
            return False

    def get_invoice(self, invoice_id: str) -> Optional[Dict]:
        """Get invoice by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoices WHERE invoice_id = ?", (invoice_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_invoices(self, limit: int = 100, status: Optional[str] = None) -> List[Dict]:
        """Get all invoices with optional status filter."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if status:
                cursor.execute(
                    "SELECT * FROM invoices WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM invoices ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )

            return [dict(row) for row in cursor.fetchall()]

    def get_pending_approvals(self) -> List[Dict]:
        """Get all invoices pending approval."""
        return self.get_all_invoices(status="pending_approval")

    def get_approved_invoices(self, limit: int = 100) -> List[Dict]:
        """Get all approved invoices."""
        return self.get_all_invoices(limit=limit, status="approved")

    def update_invoice_status(self, invoice_id: str, new_status: str) -> bool:
        """Update invoice status."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE invoices
                    SET status = ?, updated_at = ?
                    WHERE invoice_id = ?
                """, (new_status, datetime.now().isoformat(), invoice_id))
            return True
        except Exception as e:
            print(f"Error updating invoice status: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total invoices
            cursor.execute("SELECT COUNT(*) as total FROM invoices")
            total = cursor.fetchone()["total"]

            # By status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM invoices
                GROUP BY status
            """)
            by_status = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Total amount
            cursor.execute("SELECT SUM(total_amount) as total_amount FROM invoices")
            total_amount = cursor.fetchone()["total_amount"] or 0

            # Average processing time
            cursor.execute("SELECT AVG(processing_time_ms) as avg_time FROM invoices")
            avg_time = cursor.fetchone()["avg_time"] or 0

            return {
                "total_invoices": total,
                "by_status": by_status,
                "total_amount": total_amount,
                "avg_processing_time_ms": round(avg_time, 2)
            }

    def export_to_json(self, output_path: str, status: Optional[str] = None):
        """Export invoices to JSON file."""
        invoices = self.get_all_invoices(limit=10000, status=status)

        with open(output_path, 'w') as f:
            json.dump(invoices, f, indent=2, default=str)

        return len(invoices)

    def export_to_csv(self, output_path: str, status: Optional[str] = None):
        """Export invoices to CSV file."""
        import csv

        invoices = self.get_all_invoices(limit=10000, status=status)

        if not invoices:
            return 0

        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=invoices[0].keys())
            writer.writeheader()
            writer.writerows(invoices)

        return len(invoices)


# Singleton instance
_db_instance = None


def get_database() -> InvoiceDatabase:
    """Get singleton database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = InvoiceDatabase()
    return _db_instance

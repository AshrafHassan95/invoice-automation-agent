"""Test database persistence functionality."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.agents.invoice_agent import create_invoice_agent
from src.database.invoice_db import get_database

async def test_database():
    """Test database integration."""
    print("="*60)
    print("Testing Database Persistence")
    print("="*60)

    # Create agent with database enabled
    print("\n1. Creating invoice agent with database...")
    agent = create_invoice_agent()

    if agent.db:
        print("   [OK] Database initialized successfully")
        print(f"   Database location: data/invoices.db")
    else:
        print("   [FAIL] Database initialization failed")
        return

    # Process an invoice
    print("\n2. Processing invoice...")
    invoice_path = "data/uploads/607078e3_Invoice-QQP4SA6U-0003.pdf"

    if not Path(invoice_path).exists():
        print(f"   [FAIL] Invoice file not found: {invoice_path}")
        return

    result = await agent.process_invoice(invoice_path)
    print(f"   [OK] Invoice processed: {result.invoice_id}")
    print(f"   Status: {result.status.value}")

    # Query database
    print("\n3. Querying database...")
    db = get_database()

    # Get all invoices
    all_invoices = db.get_all_invoices(limit=10)
    print(f"   Total invoices in database: {len(all_invoices)}")

    # Get specific invoice
    invoice = db.get_invoice(result.invoice_id)
    if invoice:
        print(f"   [OK] Retrieved invoice from database:")
        print(f"     - ID: {invoice['invoice_id']}")
        print(f"     - Vendor: {invoice['vendor_name']}")
        print(f"     - Amount: ${invoice['total_amount']}")
        print(f"     - Status: {invoice['status']}")

    # Get statistics
    print("\n4. Database statistics...")
    stats = db.get_statistics()
    print(f"   Total invoices: {stats['total_invoices']}")
    print(f"   Total amount: ${stats['total_amount']:,.2f}")
    print(f"   Avg processing time: {stats['avg_processing_time_ms']:.2f}ms")
    print(f"   By status: {stats['by_status']}")

    # Test export
    print("\n5. Testing export functionality...")
    json_path = "data/exports/test_export.json"
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)

    count = db.export_to_json(json_path)
    print(f"   [OK] Exported {count} invoices to {json_path}")

    csv_path = "data/exports/test_export.csv"
    count = db.export_to_csv(csv_path)
    print(f"   [OK] Exported {count} invoices to {csv_path}")

    print("\n"+"="*60)
    print("Database Test Complete!")
    print("="*60)
    print("\nNext steps:")
    print("1. Check database: data/invoices.db")
    print("2. View exports: data/exports/")
    print("3. Query via API: http://localhost:8000/api/database/invoices")
    print("4. Integrate with ERP: See DATA_STORAGE_GUIDE.md")

if __name__ == "__main__":
    asyncio.run(test_database())

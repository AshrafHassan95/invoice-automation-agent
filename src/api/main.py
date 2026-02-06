"""
FastAPI Web Application for Invoice Automation Agent.

Provides:
- REST API endpoints for invoice processing
- Web interface with drag-and-drop upload
- Real-time processing status
- Dashboard with metrics
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import our agent system
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.agents.invoice_agent import create_invoice_agent
from src.utils.config import get_settings

# Initialize FastAPI app
app = FastAPI(
    title="Invoice Automation Agent",
    description="Intelligent Document Processing with Agentic AI for P2P Automation",
    version="1.0.0"
)

# Global agent instance
invoice_agent = None
settings = get_settings()

# Ensure directories exist
UPLOAD_DIR = Path("./data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# Response Models
class ProcessingResponse(BaseModel):
    """Response model for invoice processing."""
    success: bool
    invoice_id: str
    status: str
    message: str
    data: Optional[dict] = None
    processing_time_ms: int = 0


class MetricsResponse(BaseModel):
    """Response model for metrics."""
    total_processed: int
    successful: int
    failed: int
    success_rate: str
    auto_approved: int
    manual_review: int
    exceptions: int
    avg_processing_time_ms: float
    automation_rate: str


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize the invoice processing agent on startup."""
    global invoice_agent
    invoice_agent = create_invoice_agent()
    print("Invoice Processing Agent initialized")


# API Endpoints
@app.post("/api/process", response_model=ProcessingResponse)
async def process_invoice(file: UploadFile = File(...)):
    """
    Process a single invoice document.

    Upload a PDF or image file to extract invoice data,
    validate against business rules, and route for approval.
    """
    # Validate file type
    allowed_extensions = [".pdf", ".png", ".jpg", ".jpeg"]
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {allowed_extensions}"
        )

    # Save uploaded file
    file_id = str(uuid.uuid4())[:8]
    file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # Process the invoice
    try:
        result = await invoice_agent.process_invoice(str(file_path))

        return ProcessingResponse(
            success=result.success,
            invoice_id=result.invoice_id,
            status=result.status.value,
            message="Invoice processed successfully" if result.success else "Processing completed with issues",
            data={
                "invoice_data": result.invoice_data,
                "validation": result.validation,
                "approval": result.approval,
                "agent_actions": result.agent_actions,
                "errors": result.errors,
                "file_path": str(file_path)  # Include file path for deletion
            },
            processing_time_ms=result.processing_time_ms
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {e}")


@app.post("/api/process-batch")
async def process_batch(files: List[UploadFile] = File(...)):
    """Process multiple invoice documents."""
    results = []

    for file in files:
        file_id = str(uuid.uuid4())[:8]
        file_path = UPLOAD_DIR / f"{file_id}_{file.filename}"

        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            result = await invoice_agent.process_invoice(str(file_path))
            results.append({
                "filename": file.filename,
                "invoice_id": result.invoice_id,
                "success": result.success,
                "status": result.status.value
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })

    return {"processed": len(results), "results": results}


@app.get("/api/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Get processing metrics and statistics."""
    metrics = invoice_agent.get_metrics()
    return MetricsResponse(**metrics)


@app.get("/api/history")
async def get_history(limit: int = 10):
    """Get recent processing history."""
    history = invoice_agent.get_processing_history(limit)
    return {"history": history}


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@app.get("/api/database/invoices")
async def get_all_invoices_db(limit: int = 100, status: Optional[str] = None):
    """Get all invoices from database."""
    if not invoice_agent.db:
        raise HTTPException(status_code=503, detail="Database not enabled")

    invoices = invoice_agent.db.get_all_invoices(limit=limit, status=status)
    return {"invoices": invoices, "count": len(invoices)}


@app.get("/api/database/invoice/{invoice_id}")
async def get_invoice_db(invoice_id: str):
    """Get specific invoice from database."""
    if not invoice_agent.db:
        raise HTTPException(status_code=503, detail="Database not enabled")

    invoice = invoice_agent.db.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return invoice


@app.get("/api/database/statistics")
async def get_database_statistics():
    """Get database statistics."""
    if not invoice_agent.db:
        raise HTTPException(status_code=503, detail="Database not enabled")

    return invoice_agent.db.get_statistics()


@app.get("/api/export/json")
async def export_invoices_json(status: Optional[str] = None):
    """Export invoices to JSON file."""
    if not invoice_agent.db:
        raise HTTPException(status_code=503, detail="Database not enabled")

    output_path = f"data/exports/invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    count = invoice_agent.db.export_to_json(output_path, status=status)

    return {
        "success": True,
        "file_path": output_path,
        "invoice_count": count,
        "message": f"Exported {count} invoices to {output_path}"
    }


@app.get("/api/export/csv")
async def export_invoices_csv(status: Optional[str] = None):
    """Export invoices to CSV file."""
    if not invoice_agent.db:
        raise HTTPException(status_code=503, detail="Database not enabled")

    output_path = f"data/exports/invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    count = invoice_agent.db.export_to_csv(output_path, status=status)

    return {
        "success": True,
        "file_path": output_path,
        "invoice_count": count,
        "message": f"Exported {count} invoices to {output_path}"
    }


@app.delete("/api/file/{file_path:path}")
async def delete_file(file_path: str):
    """Delete an uploaded file."""
    try:
        # Ensure the file path is within the upload directory
        full_path = Path(file_path)

        # Security check: ensure path is within upload directory
        if not str(full_path).startswith(str(UPLOAD_DIR)):
            raise HTTPException(
                status_code=400,
                detail="Invalid file path"
            )

        # Delete the file if it exists
        if full_path.exists():
            full_path.unlink()
            return {"success": True, "message": "File deleted successfully"}
        else:
            return {"success": False, "message": "File not found"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")


@app.get("/api/approvals/pending")
async def get_pending_approvals():
    """Get all invoices pending approval."""
    # Filter processing history for pending approvals
    pending = []
    for record in invoice_agent.get_processing_history(limit=100):
        result = record.get("result", {})
        if result.get("status") == "pending_approval":
            pending.append({
                "invoice_id": result.get("invoice_id"),
                "timestamp": record.get("timestamp"),
                "invoice_data": result.get("invoice_data"),
                "validation": result.get("validation"),
                "approval": result.get("approval"),
                "document_path": record.get("document_path")
            })

    return {"pending_approvals": pending, "count": len(pending)}


class ApprovalAction(BaseModel):
    """Request model for approval actions."""
    invoice_id: str
    action: str  # "approve" or "reject"
    approver_name: str
    approver_email: str
    comments: Optional[str] = None


@app.post("/api/approvals/action")
async def process_approval_action(action: ApprovalAction):
    """Process an approval action (approve/reject)."""
    if action.action not in ["approve", "reject"]:
        raise HTTPException(
            status_code=400,
            detail="Action must be 'approve' or 'reject'"
        )

    # Find the invoice in history
    invoice_record = None
    for record in invoice_agent.processing_history:
        if record.get("result", {}).get("invoice_id") == action.invoice_id:
            invoice_record = record
            break

    if not invoice_record:
        raise HTTPException(
            status_code=404,
            detail=f"Invoice {action.invoice_id} not found"
        )

    # Update the invoice status
    result = invoice_record.get("result", {})

    if action.action == "approve":
        result["status"] = "approved"
        message = f"Invoice {action.invoice_id} approved by {action.approver_name}"
    else:
        result["status"] = "rejected"
        message = f"Invoice {action.invoice_id} rejected by {action.approver_name}"

    # Add approval decision to result
    result["approval_decision"] = {
        "action": action.action,
        "approver_name": action.approver_name,
        "approver_email": action.approver_email,
        "comments": action.comments,
        "timestamp": datetime.now().isoformat()
    }

    return {
        "success": True,
        "message": message,
        "invoice_id": action.invoice_id,
        "new_status": result["status"]
    }


# Web Interface
@app.get("/approvals", response_class=HTMLResponse)
async def approvals_dashboard():
    """Serve the approver dashboard."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Approval Dashboard - Invoice Automation</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <!-- Header -->
        <header class="mb-8">
            <div class="flex justify-between items-center">
                <div>
                    <h1 class="text-3xl font-bold text-gray-800">Approval Dashboard</h1>
                    <p class="text-gray-600">Review and approve pending invoices</p>
                </div>
                <a href="/" class="bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg">
                    Back to Upload
                </a>
            </div>
        </header>

        <!-- Pending Approvals -->
        <div class="bg-white rounded-xl shadow-lg p-6">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-semibold text-gray-700">Pending Approvals</h2>
                <button onclick="refreshApprovals()" class="bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 px-4 rounded-lg">
                    Refresh
                </button>
            </div>

            <div id="pendingList" class="space-y-4">
                <div class="text-center py-8 text-gray-400">
                    <p>Loading pending approvals...</p>
                </div>
            </div>
        </div>
    </div>

    <!-- Approval Modal -->
    <div id="approvalModal" class="hidden fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div class="bg-white rounded-xl shadow-2xl p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <h2 class="text-2xl font-bold mb-4 text-gray-800">Review Invoice</h2>

            <div id="modalContent" class="space-y-4">
                <!-- Invoice details will be injected here -->
            </div>

            <div class="mt-6 border-t pt-4">
                <h3 class="font-semibold mb-3">Your Decision</h3>
                <div class="space-y-3">
                    <input type="text" id="approverName" placeholder="Your Name" class="w-full border rounded-lg p-2">
                    <input type="email" id="approverEmail" placeholder="Your Email" class="w-full border rounded-lg p-2">
                    <textarea id="approverComments" placeholder="Comments (optional)" class="w-full border rounded-lg p-2 h-20"></textarea>

                    <div class="flex gap-3">
                        <button onclick="submitApproval('approve')" class="flex-1 bg-green-600 hover:bg-green-700 text-white py-3 rounded-lg font-semibold">
                            Approve
                        </button>
                        <button onclick="submitApproval('reject')" class="flex-1 bg-red-600 hover:bg-red-700 text-white py-3 rounded-lg font-semibold">
                            Reject
                        </button>
                        <button onclick="closeModal()" class="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-700 py-3 rounded-lg font-semibold">
                            Cancel
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentInvoiceId = null;

        async function refreshApprovals() {
            try {
                const response = await fetch('/api/approvals/pending');
                const data = await response.json();

                const listContainer = document.getElementById('pendingList');

                if (data.count === 0) {
                    listContainer.innerHTML = `
                        <div class="text-center py-8 text-gray-400">
                            <p>No pending approvals at this time</p>
                        </div>
                    `;
                    return;
                }

                listContainer.innerHTML = data.pending_approvals.map(approval => {
                    const invoiceData = approval.invoice_data || {};
                    const approvalInfo = approval.approval || {};

                    return `
                        <div class="border rounded-lg p-4 hover:bg-gray-50 transition">
                            <div class="flex justify-between items-start">
                                <div class="flex-1">
                                    <div class="flex items-center gap-2 mb-2">
                                        <span class="text-lg font-semibold">${invoiceData.vendor_name || 'N/A'}</span>
                                        <span class="px-2 py-1 bg-yellow-100 text-yellow-800 text-xs rounded-full">
                                            ${approvalInfo.approval_level || 'PENDING'}
                                        </span>
                                    </div>
                                    <div class="grid grid-cols-2 gap-2 text-sm text-gray-600">
                                        <div>Invoice #: <span class="font-medium">${invoiceData.invoice_number || 'N/A'}</span></div>
                                        <div>Amount: <span class="font-medium">$${(invoiceData.total_amount || 0).toLocaleString()}</span></div>
                                        <div>Date: <span class="font-medium">${invoiceData.invoice_date || 'N/A'}</span></div>
                                        <div>Priority: <span class="font-medium">${approvalInfo.priority || 'normal'}</span></div>
                                    </div>
                                </div>
                                <button onclick="openApprovalModal('${approval.invoice_id}')"
                                        class="bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg">
                                    Review
                                </button>
                            </div>
                        </div>
                    `;
                }).join('');

            } catch (error) {
                console.error('Failed to fetch approvals:', error);
                document.getElementById('pendingList').innerHTML = `
                    <div class="text-center py-8 text-red-600">
                        <p>Error loading approvals</p>
                    </div>
                `;
            }
        }

        async function openApprovalModal(invoiceId) {
            currentInvoiceId = invoiceId;

            // Fetch full invoice details
            const response = await fetch('/api/approvals/pending');
            const data = await response.json();

            const approval = data.pending_approvals.find(a => a.invoice_id === invoiceId);
            if (!approval) return;

            const invoiceData = approval.invoice_data || {};
            const validation = approval.validation || {};
            const approvalInfo = approval.approval || {};

            document.getElementById('modalContent').innerHTML = `
                <div class="bg-gray-50 rounded-lg p-4">
                    <h3 class="font-semibold mb-3">Invoice Details</h3>
                    <div class="grid grid-cols-2 gap-3 text-sm">
                        <div><span class="text-gray-600">Invoice ID:</span> <span class="font-medium">${invoiceId}</span></div>
                        <div><span class="text-gray-600">Invoice #:</span> <span class="font-medium">${invoiceData.invoice_number || 'N/A'}</span></div>
                        <div><span class="text-gray-600">Vendor:</span> <span class="font-medium">${invoiceData.vendor_name || 'N/A'}</span></div>
                        <div><span class="text-gray-600">Amount:</span> <span class="font-medium">$${(invoiceData.total_amount || 0).toLocaleString()}</span></div>
                        <div><span class="text-gray-600">Date:</span> <span class="font-medium">${invoiceData.invoice_date || 'N/A'}</span></div>
                        <div><span class="text-gray-600">Currency:</span> <span class="font-medium">${invoiceData.currency || 'USD'}</span></div>
                    </div>
                </div>

                <div class="bg-gray-50 rounded-lg p-4">
                    <h3 class="font-semibold mb-3">Approval Requirements</h3>
                    <div class="space-y-2 text-sm">
                        <div><span class="text-gray-600">Level:</span> <span class="font-medium">${approvalInfo.approval_level || 'N/A'}</span></div>
                        <div><span class="text-gray-600">Assigned To:</span> <span class="font-medium">${approvalInfo.assigned_to || 'N/A'}</span></div>
                        <div><span class="text-gray-600">Priority:</span> <span class="font-medium">${approvalInfo.priority || 'normal'}</span></div>
                        <div><span class="text-gray-600">Reason:</span> <span class="font-medium">${approvalInfo.reason || 'N/A'}</span></div>
                    </div>
                </div>

                <div class="bg-gray-50 rounded-lg p-4">
                    <h3 class="font-semibold mb-3">Validation Status</h3>
                    <div class="text-sm">
                        <div><span class="text-gray-600">Status:</span>
                            <span class="font-medium ${validation.overall_status === 'passed' ? 'text-green-600' : 'text-yellow-600'}">
                                ${(validation.overall_status || 'unknown').toUpperCase()}
                            </span>
                        </div>
                    </div>
                </div>
            `;

            document.getElementById('approvalModal').classList.remove('hidden');
        }

        function closeModal() {
            document.getElementById('approvalModal').classList.add('hidden');
            currentInvoiceId = null;
        }

        async function submitApproval(action) {
            const approverName = document.getElementById('approverName').value;
            const approverEmail = document.getElementById('approverEmail').value;
            const comments = document.getElementById('approverComments').value;

            if (!approverName || !approverEmail) {
                alert('Please provide your name and email');
                return;
            }

            try {
                const response = await fetch('/api/approvals/action', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        invoice_id: currentInvoiceId,
                        action: action,
                        approver_name: approverName,
                        approver_email: approverEmail,
                        comments: comments || null
                    })
                });

                const result = await response.json();

                if (result.success) {
                    alert(result.message);
                    closeModal();
                    refreshApprovals();
                } else {
                    alert('Failed to process approval');
                }

            } catch (error) {
                console.error('Approval error:', error);
                alert('Error processing approval');
            }
        }

        // Initial load
        refreshApprovals();

        // Auto-refresh every 30 seconds
        setInterval(refreshApprovals, 30000);
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main web interface."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Invoice Automation Agent</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .drop-zone {
            border: 3px dashed #cbd5e1;
            transition: all 0.3s ease;
        }
        .drop-zone.drag-over {
            border-color: #3b82f6;
            background-color: #eff6ff;
        }
        .agent-step {
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .processing {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <!-- Header -->
        <header class="mb-8">
            <div class="flex justify-between items-center">
                <div class="text-center flex-1">
                    <h1 class="text-4xl font-bold text-gray-800 mb-2">Invoice Automation Agent</h1>
                    <p class="text-gray-600">Intelligent Document Processing with Agentic AI</p>
                    <p class="text-sm text-gray-500 mt-1">P2P Process Automation | IDP | Business Rules Validation</p>
                </div>
                <a href="/approvals" class="bg-purple-600 hover:bg-purple-700 text-white py-2 px-4 rounded-lg flex items-center gap-2">
                    <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path>
                    </svg>
                    Approvals
                </a>
            </div>
        </header>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Upload Section -->
            <div class="lg:col-span-2">
                <div class="bg-white rounded-xl shadow-lg p-6">
                    <h2 class="text-xl font-semibold mb-4 text-gray-700">Upload Invoice</h2>

                    <!-- Drop Zone -->
                    <div id="dropZone" class="drop-zone rounded-lg p-12 text-center cursor-pointer mb-4">
                        <svg class="mx-auto h-16 w-16 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                        </svg>
                        <p class="text-gray-600 mb-2">Drag and drop invoice here</p>
                        <p class="text-gray-400 text-sm">or use the Upload button below</p>
                        <p class="text-gray-400 text-xs mt-2">Supported: PDF, PNG, JPG</p>
                        <input type="file" id="fileInput" class="hidden" accept=".pdf,.png,.jpg,.jpeg">
                    </div>

                    <!-- File Info Display -->
                    <div id="fileInfo" class="hidden mb-4 p-3 bg-gray-50 rounded-lg flex items-center justify-between">
                        <div class="flex items-center">
                            <svg class="h-5 w-5 text-blue-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                            </svg>
                            <span id="fileName" class="text-sm font-medium text-gray-700"></span>
                        </div>
                        <button onclick="removeFile()" class="text-red-600 hover:text-red-800 text-sm">Remove</button>
                    </div>

                    <!-- Control Buttons -->
                    <div class="grid grid-cols-4 gap-2 mb-4">
                        <button id="uploadBtn" onclick="triggerFileSelect()" class="bg-blue-600 hover:bg-blue-700 text-white py-3 px-4 rounded-lg transition flex items-center justify-center">
                            <svg class="h-5 w-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                            </svg>
                            Upload
                        </button>
                        <button id="startBtn" onclick="startProcessing()" disabled class="bg-green-600 hover:bg-green-700 text-white py-3 px-4 rounded-lg transition flex items-center justify-center disabled:bg-gray-300 disabled:cursor-not-allowed">
                            <svg class="h-5 w-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path>
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                            </svg>
                            Start
                        </button>
                        <button id="stopBtn" onclick="stopProcessing()" disabled class="bg-red-600 hover:bg-red-700 text-white py-3 px-4 rounded-lg transition flex items-center justify-center disabled:bg-gray-300 disabled:cursor-not-allowed">
                            <svg class="h-5 w-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"></path>
                            </svg>
                            Stop
                        </button>
                        <button id="clearBtn" onclick="clearAll()" class="bg-gray-600 hover:bg-gray-700 text-white py-3 px-4 rounded-lg transition flex items-center justify-center">
                            <svg class="h-5 w-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                            </svg>
                            Clear
                        </button>
                    </div>

                    <!-- Processing Status -->
                    <div id="processingStatus" class="hidden">
                        <div class="bg-blue-50 rounded-lg p-4 mb-4">
                            <div class="flex items-center">
                                <div class="processing mr-3">
                                    <svg class="animate-spin h-5 w-5 text-blue-600" fill="none" viewBox="0 0 24 24">
                                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                </div>
                                <span id="statusText" class="text-blue-700 font-medium">Processing invoice...</span>
                            </div>
                        </div>
                    </div>

                    <!-- Agent Activity Log -->
                    <div id="agentLog" class="hidden">
                        <h3 class="text-lg font-semibold mb-3 text-gray-700">Agent Activity</h3>
                        <div id="agentSteps" class="space-y-2 max-h-64 overflow-y-auto">
                        </div>
                    </div>
                </div>

                <!-- Results Section -->
                <div id="resultsSection" class="hidden mt-6 bg-white rounded-xl shadow-lg p-6">
                    <h2 class="text-xl font-semibold mb-4 text-gray-700">Processing Results</h2>
                    <div id="resultsContent"></div>
                </div>
            </div>

            <!-- Metrics Sidebar -->
            <div class="lg:col-span-1">
                <div class="bg-white rounded-xl shadow-lg p-6 sticky top-4">
                    <h2 class="text-xl font-semibold mb-4 text-gray-700">Processing Metrics</h2>
                    <div id="metricsContent" class="space-y-4">
                        <div class="text-center py-8 text-gray-400">
                            <p>No invoices processed yet</p>
                        </div>
                    </div>
                    <button onclick="refreshMetrics()" class="mt-4 w-full bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 rounded-lg transition">
                        Refresh Metrics
                    </button>
                </div>

                <!-- Technology Stack -->
                <div class="bg-white rounded-xl shadow-lg p-6 mt-6">
                    <h2 class="text-lg font-semibold mb-3 text-gray-700">Technology Stack</h2>
                    <div class="space-y-2 text-sm">
                        <div class="flex items-center">
                            <span class="w-3 h-3 bg-green-500 rounded-full mr-2"></span>
                            <span>Agentic AI (ReAct Pattern)</span>
                        </div>
                        <div class="flex items-center">
                            <span class="w-3 h-3 bg-blue-500 rounded-full mr-2"></span>
                            <span>IDP (Document Intelligence)</span>
                        </div>
                        <div class="flex items-center">
                            <span class="w-3 h-3 bg-purple-500 rounded-full mr-2"></span>
                            <span>Python + FastAPI</span>
                        </div>
                        <div class="flex items-center">
                            <span class="w-3 h-3 bg-orange-500 rounded-full mr-2"></span>
                            <span>P2P Process Automation</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <footer class="text-center mt-8 text-gray-500 text-sm">
            <p>Invoice Automation Agent v1.0.0 | Built with Python, FastAPI, and Agentic AI</p>
            <p class="mt-1">Demonstrating: IDP, RPA Concepts, AI/ML, Process Automation</p>
        </footer>
    </div>

    <script>
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');
        const processingStatus = document.getElementById('processingStatus');
        const statusText = document.getElementById('statusText');
        const agentLog = document.getElementById('agentLog');
        const agentSteps = document.getElementById('agentSteps');
        const resultsSection = document.getElementById('resultsSection');
        const resultsContent = document.getElementById('resultsContent');
        const fileInfo = document.getElementById('fileInfo');
        const fileName = document.getElementById('fileName');
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');

        // State management
        let selectedFile = null;
        let uploadedFilePath = null;  // Track server file path
        let isProcessing = false;
        let abortController = null;

        // Drag and drop handlers
        dropZone.addEventListener('click', () => {
            if (!isProcessing) {
                fileInput.click();
            }
        });

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (!isProcessing) {
                dropZone.classList.add('drag-over');
            }
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            if (!isProcessing) {
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    selectFile(files[0]);
                }
            }
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                selectFile(e.target.files[0]);
            }
        });

        // Button handlers
        function triggerFileSelect() {
            if (!isProcessing) {
                fileInput.click();
            }
        }

        function selectFile(file) {
            selectedFile = file;
            fileName.textContent = file.name;
            fileInfo.classList.remove('hidden');
            startBtn.disabled = false;
            dropZone.style.borderColor = '#10b981';
        }

        function removeFile() {
            selectedFile = null;
            uploadedFilePath = null;
            fileInfo.classList.add('hidden');
            startBtn.disabled = true;
            fileInput.value = '';
            dropZone.style.borderColor = '';
        }

        function startProcessing() {
            if (selectedFile && !isProcessing) {
                processFile(selectedFile);
            }
        }

        function stopProcessing() {
            if (isProcessing && abortController) {
                abortController.abort();
                isProcessing = false;
                updateButtonStates();
                statusText.textContent = 'Processing stopped by user';
                processingStatus.querySelector('div').classList.remove('bg-blue-50');
                processingStatus.querySelector('div').classList.add('bg-yellow-50');
                addAgentStep('System', 'Processing cancelled', 'red');
            }
        }

        async function clearAll() {
            // Delete uploaded file from server if exists
            if (uploadedFilePath) {
                try {
                    await fetch(`/api/file/${encodeURIComponent(uploadedFilePath)}`, {
                        method: 'DELETE'
                    });
                    uploadedFilePath = null;
                } catch (error) {
                    console.error('Failed to delete file:', error);
                }
            }

            // Clear file selection
            removeFile();

            // Clear results
            resultsSection.classList.add('hidden');
            processingStatus.classList.add('hidden');
            agentLog.classList.add('hidden');
            agentSteps.innerHTML = '';

            // Reset status
            processingStatus.querySelector('div').classList.remove('bg-green-50', 'bg-red-50', 'bg-yellow-50');
            processingStatus.querySelector('div').classList.add('bg-blue-50');

            // Reset processing state
            isProcessing = false;
            updateButtonStates();
        }

        function updateButtonStates() {
            startBtn.disabled = !selectedFile || isProcessing;
            stopBtn.disabled = !isProcessing;
            document.getElementById('uploadBtn').disabled = isProcessing;
            document.getElementById('clearBtn').disabled = isProcessing;
        }

        async function processFile(file) {
            // Set processing state
            isProcessing = true;
            updateButtonStates();

            // Show processing status
            processingStatus.classList.remove('hidden');
            agentLog.classList.remove('hidden');
            resultsSection.classList.add('hidden');
            agentSteps.innerHTML = '';

            // Reset status styling
            processingStatus.querySelector('div').classList.remove('bg-green-50', 'bg-red-50', 'bg-yellow-50');
            processingStatus.querySelector('div').classList.add('bg-blue-50');
            statusText.textContent = 'Processing invoice...';

            // Add initial step
            addAgentStep('Extraction Agent', 'Analyzing document...', 'blue');

            const formData = new FormData();
            formData.append('file', file);

            // Create abort controller for stop functionality
            abortController = new AbortController();

            try {
                const response = await fetch('/api/process', {
                    method: 'POST',
                    body: formData,
                    signal: abortController.signal
                });

                const result = await response.json();

                // Store uploaded file path for deletion
                if (result.data && result.data.file_path) {
                    uploadedFilePath = result.data.file_path;
                }

                // Update status
                statusText.textContent = result.success ? 'Processing complete!' : 'Processing completed with issues';
                processingStatus.querySelector('div').classList.remove('bg-blue-50');
                processingStatus.querySelector('div').classList.add(result.success ? 'bg-green-50' : 'bg-yellow-50');

                // Show results
                displayResults(result);
                refreshMetrics();

            } catch (error) {
                if (error.name === 'AbortError') {
                    // Request was cancelled, already handled in stopProcessing()
                } else {
                    statusText.textContent = 'Error processing invoice';
                    processingStatus.querySelector('div').classList.remove('bg-blue-50');
                    processingStatus.querySelector('div').classList.add('bg-red-50');
                    addAgentStep('Error', error.message, 'red');
                }
            } finally {
                // Reset processing state
                isProcessing = false;
                abortController = null;
                updateButtonStates();
            }
        }

        function addAgentStep(agent, action, color) {
            const colorClasses = {
                blue: 'bg-blue-100 text-blue-800 border-blue-200',
                purple: 'bg-purple-100 text-purple-800 border-purple-200',
                green: 'bg-green-100 text-green-800 border-green-200',
                red: 'bg-red-100 text-red-800 border-red-200'
            };

            const step = document.createElement('div');
            step.className = `agent-step p-3 rounded-lg border ${colorClasses[color]}`;
            step.innerHTML = `<span class="font-medium">${agent}:</span> ${action}`;
            agentSteps.appendChild(step);
            agentSteps.scrollTop = agentSteps.scrollHeight;
        }

        function displayResults(result) {
            resultsSection.classList.remove('hidden');

            const data = result.data || {};
            const invoiceData = data.invoice_data || {};
            const approval = data.approval || {};

            resultsContent.innerHTML = `
                <div class="grid grid-cols-2 gap-4 mb-4">
                    <div class="p-4 bg-gray-50 rounded-lg">
                        <p class="text-sm text-gray-500">Invoice ID</p>
                        <p class="font-semibold">${result.invoice_id}</p>
                    </div>
                    <div class="p-4 bg-gray-50 rounded-lg">
                        <p class="text-sm text-gray-500">Status</p>
                        <p class="font-semibold ${result.success ? 'text-green-600' : 'text-yellow-600'}">${result.status.toUpperCase()}</p>
                    </div>
                </div>

                ${invoiceData ? `
                <div class="mb-4">
                    <h3 class="font-semibold mb-2">Extracted Data</h3>
                    <div class="grid grid-cols-2 gap-2 text-sm">
                        <div><span class="text-gray-500">Vendor:</span> ${invoiceData.vendor_name || 'N/A'}</div>
                        <div><span class="text-gray-500">Invoice #:</span> ${invoiceData.invoice_number || 'N/A'}</div>
                        <div><span class="text-gray-500">Amount:</span> $${(invoiceData.total_amount || 0).toLocaleString()}</div>
                        <div><span class="text-gray-500">Date:</span> ${invoiceData.invoice_date || 'N/A'}</div>
                    </div>
                </div>
                ` : ''}

                ${approval ? `
                <div class="mb-4">
                    <h3 class="font-semibold mb-2">Routing Decision</h3>
                    <div class="grid grid-cols-2 gap-2 text-sm">
                        <div><span class="text-gray-500">Approval Level:</span> ${approval.approval_level || 'N/A'}</div>
                        <div><span class="text-gray-500">Assigned To:</span> ${approval.assigned_to || 'N/A'}</div>
                        <div><span class="text-gray-500">Priority:</span> ${approval.priority || 'N/A'}</div>
                        <div><span class="text-gray-500">Deadline:</span> ${approval.sla_deadline ? new Date(approval.sla_deadline).toLocaleString() : 'N/A'}</div>
                    </div>
                </div>
                ` : ''}

                <div class="text-sm text-gray-500">
                    Processing time: ${result.processing_time_ms}ms
                </div>
            `;
        }

        async function refreshMetrics() {
            try {
                const response = await fetch('/api/metrics');
                const metrics = await response.json();

                document.getElementById('metricsContent').innerHTML = `
                    <div class="grid grid-cols-2 gap-3">
                        <div class="text-center p-3 bg-blue-50 rounded-lg">
                            <p class="text-2xl font-bold text-blue-600">${metrics.total_processed}</p>
                            <p class="text-xs text-gray-500">Total Processed</p>
                        </div>
                        <div class="text-center p-3 bg-green-50 rounded-lg">
                            <p class="text-2xl font-bold text-green-600">${metrics.success_rate}</p>
                            <p class="text-xs text-gray-500">Success Rate</p>
                        </div>
                        <div class="text-center p-3 bg-purple-50 rounded-lg">
                            <p class="text-2xl font-bold text-purple-600">${metrics.auto_approved}</p>
                            <p class="text-xs text-gray-500">Auto-Approved</p>
                        </div>
                        <div class="text-center p-3 bg-orange-50 rounded-lg">
                            <p class="text-2xl font-bold text-orange-600">${metrics.manual_review}</p>
                            <p class="text-xs text-gray-500">Manual Review</p>
                        </div>
                    </div>
                    <div class="mt-4 p-3 bg-gray-50 rounded-lg">
                        <p class="text-sm text-gray-500">Avg Processing Time</p>
                        <p class="font-semibold">${metrics.avg_processing_time_ms}ms</p>
                    </div>
                    <div class="mt-2 p-3 bg-gray-50 rounded-lg">
                        <p class="text-sm text-gray-500">Automation Rate</p>
                        <p class="font-semibold">${metrics.automation_rate}</p>
                    </div>
                `;
            } catch (error) {
                console.error('Failed to fetch metrics:', error);
            }
        }

        // Initial metrics load
        refreshMetrics();
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)

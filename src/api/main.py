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
                "errors": result.errors
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


# Web Interface
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
        <header class="text-center mb-8">
            <h1 class="text-4xl font-bold text-gray-800 mb-2">Invoice Automation Agent</h1>
            <p class="text-gray-600">Intelligent Document Processing with Agentic AI</p>
            <p class="text-sm text-gray-500 mt-1">P2P Process Automation | IDP | Business Rules Validation</p>
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
                        <p class="text-gray-400 text-sm">or click to browse</p>
                        <p class="text-gray-400 text-xs mt-2">Supported: PDF, PNG, JPG</p>
                        <input type="file" id="fileInput" class="hidden" accept=".pdf,.png,.jpg,.jpeg">
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

        // Drag and drop handlers
        dropZone.addEventListener('click', () => fileInput.click());

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                processFile(files[0]);
            }
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                processFile(e.target.files[0]);
            }
        });

        async function processFile(file) {
            // Show processing status
            processingStatus.classList.remove('hidden');
            agentLog.classList.remove('hidden');
            resultsSection.classList.add('hidden');
            agentSteps.innerHTML = '';

            // Add initial step
            addAgentStep('Extraction Agent', 'Analyzing document...', 'blue');

            const formData = new FormData();
            formData.append('file', file);

            try {
                // Simulate agent steps
                setTimeout(() => addAgentStep('Extraction Agent', 'Extracting text from PDF', 'blue'), 500);
                setTimeout(() => addAgentStep('Extraction Agent', 'Parsing invoice fields', 'blue'), 1000);
                setTimeout(() => addAgentStep('Validation Agent', 'Validating required fields', 'purple'), 1500);
                setTimeout(() => addAgentStep('Validation Agent', 'Checking vendor approval', 'purple'), 2000);
                setTimeout(() => addAgentStep('Validation Agent', 'Matching Purchase Order', 'purple'), 2500);
                setTimeout(() => addAgentStep('Routing Agent', 'Determining approval level', 'green'), 3000);

                const response = await fetch('/api/process', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                // Update status
                statusText.textContent = result.success ? 'Processing complete!' : 'Processing completed with issues';
                processingStatus.querySelector('div').classList.remove('bg-blue-50');
                processingStatus.querySelector('div').classList.add(result.success ? 'bg-green-50' : 'bg-yellow-50');

                // Show results
                displayResults(result);
                refreshMetrics();

            } catch (error) {
                statusText.textContent = 'Error processing invoice';
                processingStatus.querySelector('div').classList.remove('bg-blue-50');
                processingStatus.querySelector('div').classList.add('bg-red-50');
                addAgentStep('Error', error.message, 'red');
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

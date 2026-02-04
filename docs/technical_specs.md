# Technical Specifications

## 1. Architecture Overview

### 1.1 System Architecture
```
┌────────────────────────────────────────────────────────────────────┐
│                         Web Interface                               │
│                    (FastAPI + HTML/Tailwind)                        │
└────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│                      Invoice Processing Agent                       │
│                         (Orchestrator)                              │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐      │
│  │   Extraction    │ │   Validation    │ │    Routing      │      │
│  │     Agent       │ │     Agent       │ │     Agent       │      │
│  │     (IDP)       │ │   (Rules)       │ │   (Workflow)    │      │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘      │
└────────────────────────────────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Document      │    │    Business     │    │    Workflow     │
│   Processor     │    │    Rules        │    │    Engine       │
│   (PDF/OCR)     │    │    Engine       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 1.2 Agentic AI Pattern
This system implements the **ReAct (Reasoning + Acting)** pattern:

```python
# Agent Loop
while not task_complete:
    observation = observe_current_state()
    thought = reason_about_observation(observation)
    action = decide_next_action(thought)
    result = execute_tool(action)
    update_state(result)
```

## 2. Component Specifications

### 2.1 Base Agent (`base_agent.py`)
```python
class BaseAgent:
    """Abstract base for all agents."""

    # Tool registration
    def register_tool(tool: Tool) -> None
    def execute_tool(name: str, **kwargs) -> Any

    # Reasoning
    def record_thought(observation, reasoning, action, input) -> AgentThought

    # Execution
    async def run(input_data: Dict) -> AgentResponse
```

### 2.2 Extraction Agent (`extraction_agent.py`)
**Purpose**: Intelligent Document Processing (IDP)

**Tools**:
| Tool | Description |
|------|-------------|
| `analyze_document` | Determine document type and extraction method |
| `extract_with_ocr` | OCR extraction for scanned documents |
| `extract_with_parser` | Text extraction for digital PDFs |
| `parse_invoice_fields` | Pattern matching for field extraction |
| `validate_extraction` | Quality assurance check |

**Extraction Patterns**:
```python
patterns = {
    "invoice_number": r"(?:invoice\s*#?:?\s*)([A-Z0-9][-A-Z0-9]{2,20})",
    "date": r"(?:date:?\s*)(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
    "amount": r"(?:total|amount\s*due):?\s*[$€£]?\s*([\d,]+\.?\d{0,2})",
    "vendor_name": r"^([A-Z][A-Za-z\s&]+(?:Inc\.?|LLC|Ltd\.?))"
}
```

### 2.3 Validation Agent (`validation_agent.py`)
**Purpose**: Business rules enforcement

**Tools**:
| Tool | Description |
|------|-------------|
| `validate_required_fields` | Check mandatory fields |
| `validate_amounts` | Verify calculations |
| `validate_dates` | Check date validity |
| `verify_vendor` | Match against vendor master |
| `check_duplicate` | Detect duplicate invoices |
| `match_purchase_order` | 3-way match |

**Validation Rules**:
```python
VALIDATION_RULES = {
    "required_fields": ["vendor_name", "invoice_number", "total_amount"],
    "amount_validation": {
        "min_amount": 0.01,
        "max_amount": 10_000_000,
        "tolerance": 0.02  # 2%
    },
    "date_validation": {
        "max_age_days": 365,
        "future_allowed": False
    }
}
```

### 2.4 Routing Agent (`routing_agent.py`)
**Purpose**: Workflow automation

**Tools**:
| Tool | Description |
|------|-------------|
| `determine_approval_level` | Amount-based routing |
| `check_auto_approval_eligibility` | Auto-approve criteria |
| `route_exception` | Exception handler assignment |
| `calculate_sla` | Deadline calculation |
| `assign_approver` | Approver selection |
| `create_approval_request` | Request generation |

**Routing Rules**:
```python
ROUTING_RULES = {
    "auto_approve": {"max_amount": 5000, "requires_po": True},
    "manager_review": {"min": 5001, "max": 25000},
    "director_review": {"min": 25001, "max": 100000},
    "executive_review": {"min": 100001}
}
```

## 3. Data Models

### 3.1 Invoice Data
```python
class InvoiceData(BaseModel):
    vendor_name: str
    invoice_number: str
    invoice_date: date
    due_date: Optional[date]
    po_number: Optional[str]
    subtotal: float
    tax_amount: float
    total_amount: float
    currency: Currency
    line_items: List[LineItem]
```

### 3.2 Processing Result
```python
class ProcessingResult(BaseModel):
    invoice_id: str
    success: bool
    status: InvoiceStatus
    invoice_data: Optional[InvoiceData]
    validation: Optional[dict]
    approval: Optional[dict]
    processing_time_ms: int
    agent_actions: List[str]
    errors: List[str]
```

## 4. API Specification

### 4.1 Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/process` | Process single invoice |
| POST | `/api/process-batch` | Process multiple invoices |
| GET | `/api/metrics` | Get processing metrics |
| GET | `/api/history` | Get processing history |
| GET | `/api/health` | Health check |

### 4.2 Process Invoice Request
```http
POST /api/process
Content-Type: multipart/form-data

file: <invoice.pdf>
```

### 4.3 Process Invoice Response
```json
{
    "success": true,
    "invoice_id": "abc12345",
    "status": "approved",
    "message": "Invoice processed successfully",
    "data": {
        "invoice_data": {...},
        "validation": {...},
        "approval": {...}
    },
    "processing_time_ms": 1234
}
```

## 5. Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Web Framework | FastAPI |
| PDF Processing | PyPDF2 |
| OCR | Tesseract (pytesseract) |
| Data Validation | Pydantic |
| Async Support | asyncio |
| Frontend | HTML + Tailwind CSS |

## 6. Integration Options

### 6.1 LLM Integration (Optional)
```python
# Azure OpenAI
AZURE_OPENAI_ENDPOINT = "https://..."
AZURE_OPENAI_KEY = "..."
AZURE_OPENAI_DEPLOYMENT = "gpt-4"

# OpenAI API
OPENAI_API_KEY = "sk-..."
```

### 6.2 IDP Platform Integration
Compatible with:
- Azure Document Intelligence
- AWS Textract
- Google Document AI
- ABBYY
- Kofax

### 6.3 RPA Integration Points
- UiPath: REST API integration
- Automation Anywhere: A360 Bot
- Power Automate: Custom connector
- Blue Prism: Web API

## 7. Performance Specifications

| Metric | Target |
|--------|--------|
| Single invoice processing | <5 seconds |
| Batch processing (10 invoices) | <30 seconds |
| API response time | <100ms |
| Concurrent requests | 50+ |
| Uptime | 99.9% |

## 8. Security Considerations

- File upload validation (type, size)
- No credential storage in code
- Environment variable configuration
- Input sanitization
- Audit logging

## 9. Deployment Options

### 9.1 Local Development
```bash
pip install -r requirements.txt
uvicorn src.api.main:app --reload
```

### 9.2 Docker
```dockerfile
FROM python:3.11-slim
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0"]
```

### 9.3 Cloud Deployment
- Azure App Service
- AWS Lambda + API Gateway
- Google Cloud Run
- Kubernetes (AKS, EKS, GKE)

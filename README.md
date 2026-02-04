# Invoice Automation Agent

**Intelligent Document Processing with Agentic AI for P2P Automation**

A comprehensive Python project demonstrating enterprise automation capabilities including Agentic AI, Intelligent Document Processing (IDP), business rules validation, and workflow automation for the Procure-to-Pay (P2P) process.

---

## Project Overview

This project showcases skills relevant to automation and AI project delivery:

| Skill Area | Implementation |
|------------|----------------|
| **Agentic AI** | ReAct pattern agents with tool-using capabilities |
| **IDP** | PDF/Image extraction, OCR, pattern matching |
| **RPA Concepts** | Automated workflow, exception handling |
| **P2P Process** | Invoice validation, PO matching, approval routing |
| **Python** | FastAPI, Pydantic, async programming |
| **Business Analysis** | Process documentation, requirements translation |

---

## Key Features

### 1. Agentic AI System
- **Orchestrator Agent**: Coordinates the processing pipeline
- **Extraction Agent**: Intelligent document processing
- **Validation Agent**: Business rules enforcement
- **Routing Agent**: Workflow automation

### 2. Intelligent Document Processing
- PDF text extraction (digital documents)
- OCR support (scanned documents)
- Field extraction with pattern matching
- Confidence scoring

### 3. Business Rules Engine
- Required field validation
- Amount calculations verification
- Vendor approval checking
- Duplicate detection
- 3-way PO matching

### 4. Workflow Automation
- Amount-based approval routing
- Exception handling and assignment
- SLA calculation
- Priority determination

### 5. Web Interface
- Drag-and-drop file upload
- Real-time processing status
- Agent activity visualization
- Processing metrics dashboard

---

## Architecture

```
invoice-automation-agent/
├── src/
│   ├── agents/                    # Agentic AI Components
│   │   ├── base_agent.py          # Base agent framework (ReAct pattern)
│   │   ├── invoice_agent.py       # Main orchestrator
│   │   ├── extraction_agent.py    # IDP agent
│   │   ├── validation_agent.py    # Business rules agent
│   │   └── routing_agent.py       # Workflow agent
│   ├── processors/
│   │   └── document_processor.py  # PDF/OCR processing
│   ├── models/
│   │   └── invoice.py             # Data models (Pydantic)
│   ├── api/
│   │   └── main.py                # FastAPI web application
│   └── utils/
│       └── config.py              # Configuration & business rules
├── docs/
│   ├── process_documentation.md   # Business process documentation
│   └── technical_specs.md         # Technical specifications
├── data/                          # Runtime data (excluded from Git)
│   ├── uploads/                   # Uploaded invoice files
│   ├── processed/                 # Processed documents
│   └── output/                    # Processing results
├── run.py                         # Application entry point
├── requirements.txt
└── README.md
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- pip

### Installation
```bash
# Clone/navigate to project
cd invoice-automation-agent

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment (optional)
cp .env.example .env
# Edit .env with your API keys if using LLM features
```

### Run Application
```bash
python run.py
```
Then open http://localhost:8000

---

## Application Usage

### Web Interface
1. Start the server: `python run.py`
2. Open http://localhost:8000
3. Drag and drop an invoice (PDF/PNG/JPG)
4. Watch real-time agent processing
5. View extracted data and routing decision

### Processing Flow
1. **Upload**: Drag and drop invoice document
2. **Extraction**: Agent extracts data using IDP
3. **Validation**: Business rules verification
4. **Routing**: Automatic approval path determination
5. **Results**: View extracted data, validation status, and routing decision

---

## Technology Stack

| Category | Technologies |
|----------|-------------|
| **Language** | Python 3.11+ |
| **AI/ML** | Agentic AI (ReAct), LLM-ready (OpenAI/Azure) |
| **IDP** | PyPDF2, Tesseract OCR, Pattern Matching |
| **Web** | FastAPI, HTML, Tailwind CSS |
| **Data** | Pydantic, Pandas |
| **Async** | asyncio, concurrent processing |

---

## Business Rules Configuration

### Approval Thresholds
```python
AUTO_APPROVE_THRESHOLD = 5000.00      # Auto-approve below this
MANAGER_APPROVAL_THRESHOLD = 25000.00  # Manager required
EXECUTIVE_APPROVAL_THRESHOLD = 100000.00  # Executive required
```

### Validation Rules
```python
VALIDATION_RULES = {
    "required_fields": ["vendor_name", "invoice_number", "total_amount"],
    "amount_validation": {
        "min_amount": 0.01,
        "max_amount": 10000000.00
    },
    "tolerance_percentage": 0.02  # 2% for matching
}
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/process` | POST | Process single invoice |
| `/api/process-batch` | POST | Process multiple invoices |
| `/api/metrics` | GET | Get processing statistics |
| `/api/history` | GET | Get processing history |
| `/api/health` | GET | Health check |

---

## Relevance to Target Role

This project demonstrates capabilities aligned with the Automation & AI Specialist role:

### Technical Skills Demonstrated
- **Python**: Core programming language
- **AI/Agentic AI**: ReAct pattern, tool-using agents
- **IDP**: Document Intelligence concepts
- **RPA Understanding**: Automation patterns, exception handling
- **API Development**: FastAPI, REST endpoints

### Business Analysis Capabilities
- Process documentation
- Requirements translation to technical specs
- Business rules configuration
- Exception handling workflows

### Process Knowledge
- **P2P Process**: Procure-to-Pay automation
- **Finance Processes**: Invoice validation, PO matching
- Approval workflows
- Exception routing

---

## Production Readiness

This codebase is structured for production deployment:
- ✅ Clean directory structure
- ✅ Environment variable configuration
- ✅ Data directory excluded from version control
- ✅ Modular agent architecture
- ✅ API-first design with FastAPI
- ✅ Async processing support

## Future Enhancements

### Production-Ready Features
- [ ] Azure Document Intelligence integration
- [ ] Database persistence (PostgreSQL)
- [ ] User authentication & authorization
- [ ] Email notifications & webhooks
- [ ] Power Automate connector
- [ ] Audit logging & compliance tracking

### Advanced AI Features
- [ ] LLM-powered extraction (GPT-4)
- [ ] Anomaly detection & fraud prevention
- [ ] Smart categorization & learning
- [ ] Predictive routing based on historical data

---

## Project Structure Explanation

### `src/agents/` - Agentic AI Implementation
The core of this project. Each agent follows the ReAct pattern:
- **Observe** current state
- **Think** about what to do
- **Act** using available tools
- **Update** state and repeat

### `src/processors/` - Document Processing
IDP implementation with support for:
- Digital PDFs (text extraction)
- Scanned documents (OCR)
- Pattern-based field extraction

### `src/models/` - Data Models
Pydantic models ensuring data integrity:
- Invoice data structure
- Validation results
- Approval requests
- Agent states

### `docs/` - Business Analysis Artifacts
Documentation demonstrating BA capabilities:
- Process flows
- Business rules
- Technical specifications

---

## Contact

**Ahmad Ashraf bin Hassan**
- Email: ashraf950901@gmail.com
- LinkedIn: [linkedin.com/in/ahmadashrafhassan](https://linkedin.com/in/ahmadashrafhassan)
- GitHub: [github.com/AshrafHassan95](https://github.com/AshrafHassan95)

---

## License

This project is created for portfolio/demonstration purposes.

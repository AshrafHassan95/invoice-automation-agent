"""
Configuration management for Invoice Automation Agent.
Supports environment variables for secure credential management.
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Invoice Automation Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # AI Provider Configuration (Ollama via OpenAI-compatible API)
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"

    # Model Configuration
    LLM_MODEL: str = "llama3"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4096

    # Document Processing
    TESSERACT_PATH: Optional[str] = None
    POPPLER_PATH: Optional[str] = None
    MAX_FILE_SIZE_MB: int = 50
    SUPPORTED_FORMATS: list = [".pdf", ".png", ".jpg", ".jpeg"]

    # Business Rules - Invoice Processing
    AUTO_APPROVE_THRESHOLD: float = 5000.00  # Auto-approve if below this amount
    MANAGER_APPROVAL_THRESHOLD: float = 25000.00  # Requires manager approval
    EXECUTIVE_APPROVAL_THRESHOLD: float = 100000.00  # Requires executive approval

    # Validation Rules
    DUPLICATE_CHECK_DAYS: int = 90  # Check for duplicates within this period
    PAYMENT_TERMS_DEFAULT: int = 30  # Default NET days
    TOLERANCE_PERCENTAGE: float = 0.02  # 2% tolerance for amount matching

    # Approved Vendors (for demo - would be database in production)
    APPROVED_VENDORS: list = [
        "ACME Corporation",
        "TechSupply Inc",
        "Office Solutions Ltd",
        "Global Services Co",
        "Industrial Parts Supplier"
    ]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/invoices.db"

    # File Paths
    UPLOAD_DIR: str = "./data/uploads"
    PROCESSED_DIR: str = "./data/processed"
    OUTPUT_DIR: str = "./data/output"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Business rule configurations for the Agentic AI
VALIDATION_RULES = {
    "required_fields": [
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "total_amount",
        "currency"
    ],
    "amount_validation": {
        "min_amount": 0.01,
        "max_amount": 10000000.00,
        "currency_codes": ["USD", "EUR", "GBP", "MYR", "SGD"]
    },
    "date_validation": {
        "max_age_days": 365,  # Invoice cannot be older than 1 year
        "future_date_allowed": False
    }
}

ROUTING_RULES = {
    "auto_approve": {
        "max_amount": 5000.00,
        "requires_po_match": True,
        "requires_vendor_approved": True
    },
    "manager_review": {
        "min_amount": 5000.01,
        "max_amount": 25000.00
    },
    "director_review": {
        "min_amount": 25000.01,
        "max_amount": 100000.00
    },
    "executive_review": {
        "min_amount": 100000.01
    },
    "exception_handling": {
        "missing_po": "procurement_team",
        "vendor_not_approved": "vendor_management",
        "duplicate_suspected": "accounts_payable",
        "amount_mismatch": "requester"
    }
}

# Agent tool configurations
AGENT_TOOLS = {
    "extract_invoice_data": {
        "description": "Extract structured data from invoice document using OCR and AI",
        "parameters": ["document_path", "extraction_mode"]
    },
    "validate_invoice": {
        "description": "Validate extracted invoice data against business rules",
        "parameters": ["invoice_data", "validation_level"]
    },
    "check_duplicate": {
        "description": "Check if invoice is a potential duplicate",
        "parameters": ["vendor_name", "invoice_number", "amount", "date"]
    },
    "match_purchase_order": {
        "description": "Match invoice to existing purchase order",
        "parameters": ["po_number", "vendor_name", "amount"]
    },
    "route_for_approval": {
        "description": "Route invoice to appropriate approver based on rules",
        "parameters": ["invoice_data", "validation_results"]
    },
    "create_payment_request": {
        "description": "Create payment request for approved invoice",
        "parameters": ["invoice_data", "approval_info"]
    }
}

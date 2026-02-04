"""
Data models for Invoice Processing Automation.
These models represent the core business entities in the P2P (Procure-to-Pay) process.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, date
from enum import Enum
from decimal import Decimal


class Currency(str, Enum):
    """Supported currencies for invoice processing."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    MYR = "MYR"
    SGD = "SGD"


class InvoiceStatus(str, Enum):
    """Invoice processing status in the P2P workflow."""
    RECEIVED = "received"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    VALIDATING = "validating"
    VALIDATED = "validated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    EXCEPTION = "exception"


class ValidationStatus(str, Enum):
    """Validation result status."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    PENDING = "pending"


class ApprovalLevel(str, Enum):
    """Approval routing levels based on business rules."""
    AUTO_APPROVED = "auto_approved"
    MANAGER = "manager"
    DIRECTOR = "director"
    EXECUTIVE = "executive"
    EXCEPTION = "exception"


class ExceptionType(str, Enum):
    """Types of exceptions that require manual intervention."""
    MISSING_PO = "missing_po"
    VENDOR_NOT_APPROVED = "vendor_not_approved"
    DUPLICATE_SUSPECTED = "duplicate_suspected"
    AMOUNT_MISMATCH = "amount_mismatch"
    INVALID_DATA = "invalid_data"
    OCR_FAILED = "ocr_failed"


# ============== Line Item Models ==============

class LineItem(BaseModel):
    """Individual line item on an invoice."""
    line_number: int = Field(..., ge=1, description="Line item number")
    description: str = Field(..., min_length=1, description="Item description")
    quantity: float = Field(..., gt=0, description="Quantity ordered")
    unit_price: float = Field(..., ge=0, description="Price per unit")
    amount: float = Field(..., ge=0, description="Line total amount")
    tax_amount: Optional[float] = Field(default=0.0, description="Tax amount for line")
    po_line_reference: Optional[str] = Field(default=None, description="Reference to PO line")

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, v, info):
        """Validate line amount matches quantity * unit_price."""
        return v


# ============== Invoice Models ==============

class InvoiceData(BaseModel):
    """Extracted invoice data structure."""
    # Vendor Information
    vendor_name: str = Field(..., min_length=1, description="Vendor/Supplier name")
    vendor_address: Optional[str] = Field(default=None, description="Vendor address")
    vendor_tax_id: Optional[str] = Field(default=None, description="Vendor tax ID")

    # Invoice Details
    invoice_number: str = Field(..., min_length=1, description="Invoice number")
    invoice_date: date = Field(..., description="Invoice date")
    due_date: Optional[date] = Field(default=None, description="Payment due date")
    payment_terms: Optional[str] = Field(default=None, description="Payment terms (e.g., NET30)")

    # Purchase Order Reference
    po_number: Optional[str] = Field(default=None, description="Purchase order number")

    # Financial Details
    subtotal: float = Field(..., ge=0, description="Subtotal before tax")
    tax_amount: float = Field(default=0.0, ge=0, description="Total tax amount")
    total_amount: float = Field(..., gt=0, description="Total invoice amount")
    currency: Currency = Field(default=Currency.USD, description="Invoice currency")

    # Line Items
    line_items: List[LineItem] = Field(default=[], description="Invoice line items")

    # Metadata
    extraction_confidence: float = Field(default=0.0, ge=0, le=1, description="OCR confidence score")
    raw_text: Optional[str] = Field(default=None, description="Raw extracted text")


class Invoice(BaseModel):
    """Complete invoice entity with processing state."""
    id: Optional[str] = Field(default=None, description="Unique invoice ID")
    document_path: str = Field(..., description="Path to source document")
    data: Optional[InvoiceData] = Field(default=None, description="Extracted invoice data")
    status: InvoiceStatus = Field(default=InvoiceStatus.RECEIVED, description="Current status")
    created_at: datetime = Field(default_factory=datetime.now, description="Record creation time")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update time")
    processed_by: Optional[str] = Field(default=None, description="Agent/user who processed")


# ============== Validation Models ==============

class ValidationResult(BaseModel):
    """Result of a single validation check."""
    rule_name: str = Field(..., description="Name of validation rule")
    status: ValidationStatus = Field(..., description="Validation status")
    message: str = Field(..., description="Validation message")
    details: Optional[dict] = Field(default=None, description="Additional details")


class InvoiceValidation(BaseModel):
    """Complete validation results for an invoice."""
    invoice_id: str = Field(..., description="Invoice ID being validated")
    overall_status: ValidationStatus = Field(..., description="Overall validation status")
    validation_results: List[ValidationResult] = Field(default=[], description="Individual results")
    exceptions: List[ExceptionType] = Field(default=[], description="Detected exceptions")
    validated_at: datetime = Field(default_factory=datetime.now, description="Validation timestamp")
    validated_by: str = Field(default="validation_agent", description="Agent that performed validation")


# ============== Workflow Models ==============

class ApprovalRequest(BaseModel):
    """Approval request for invoice routing."""
    invoice_id: str = Field(..., description="Invoice ID")
    approval_level: ApprovalLevel = Field(..., description="Required approval level")
    approver_id: Optional[str] = Field(default=None, description="Assigned approver")
    reason: str = Field(..., description="Reason for this approval level")
    amount: float = Field(..., description="Invoice amount")
    vendor_name: str = Field(..., description="Vendor name")
    requested_at: datetime = Field(default_factory=datetime.now)
    due_by: Optional[datetime] = Field(default=None, description="Approval deadline")


class ProcessingResult(BaseModel):
    """Final result of invoice processing pipeline."""
    invoice_id: str = Field(..., description="Processed invoice ID")
    success: bool = Field(..., description="Processing success status")
    status: InvoiceStatus = Field(..., description="Final invoice status")
    invoice_data: Optional[InvoiceData] = Field(default=None, description="Extracted data")
    validation: Optional[InvoiceValidation] = Field(default=None, description="Validation results")
    approval: Optional[ApprovalRequest] = Field(default=None, description="Approval routing")
    processing_time_ms: int = Field(..., description="Total processing time")
    agent_actions: List[str] = Field(default=[], description="Actions taken by agents")
    errors: List[str] = Field(default=[], description="Any errors encountered")


# ============== Agent Communication Models ==============

class AgentAction(BaseModel):
    """Represents an action taken by an agent."""
    agent_name: str = Field(..., description="Name of the agent")
    action: str = Field(..., description="Action/tool used")
    input_data: dict = Field(default={}, description="Input to the action")
    output_data: dict = Field(default={}, description="Output from the action")
    reasoning: str = Field(..., description="Agent's reasoning for this action")
    timestamp: datetime = Field(default_factory=datetime.now)
    success: bool = Field(default=True, description="Whether action succeeded")


class AgentState(BaseModel):
    """Current state of the agent processing pipeline."""
    current_step: str = Field(..., description="Current processing step")
    invoice: Optional[Invoice] = Field(default=None, description="Invoice being processed")
    actions_taken: List[AgentAction] = Field(default=[], description="Actions completed")
    pending_decisions: List[str] = Field(default=[], description="Decisions to be made")
    context: dict = Field(default={}, description="Additional context for decision making")


# ============== Purchase Order Models (for matching) ==============

class PurchaseOrder(BaseModel):
    """Purchase Order for 3-way matching."""
    po_number: str = Field(..., description="PO number")
    vendor_name: str = Field(..., description="Vendor name")
    total_amount: float = Field(..., description="PO total amount")
    currency: Currency = Field(default=Currency.USD)
    status: str = Field(default="open", description="PO status")
    created_date: date = Field(..., description="PO creation date")
    line_items: List[dict] = Field(default=[], description="PO line items")


# Sample PO data for demo purposes
SAMPLE_PURCHASE_ORDERS = [
    PurchaseOrder(
        po_number="PO-2024-001",
        vendor_name="ACME Corporation",
        total_amount=4500.00,
        currency=Currency.USD,
        status="open",
        created_date=date(2024, 1, 15),
        line_items=[
            {"item": "Office Supplies", "quantity": 100, "unit_price": 45.00}
        ]
    ),
    PurchaseOrder(
        po_number="PO-2024-002",
        vendor_name="TechSupply Inc",
        total_amount=12750.00,
        currency=Currency.USD,
        status="open",
        created_date=date(2024, 1, 20),
        line_items=[
            {"item": "Laptop Computers", "quantity": 5, "unit_price": 2550.00}
        ]
    ),
    PurchaseOrder(
        po_number="PO-2024-003",
        vendor_name="Office Solutions Ltd",
        total_amount=850.00,
        currency=Currency.USD,
        status="open",
        created_date=date(2024, 2, 1),
        line_items=[
            {"item": "Printer Paper", "quantity": 50, "unit_price": 17.00}
        ]
    ),
]

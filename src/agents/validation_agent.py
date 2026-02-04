"""
Validation Agent for Invoice Business Rules.

This agent validates extracted invoice data against:
1. Data completeness rules
2. Business logic rules
3. Vendor verification
4. Duplicate detection
5. PO matching (3-way match)
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta

from .base_agent import BaseAgent, AgentRole, Tool, AgentResponse
from ..models.invoice import (
    InvoiceData, ValidationResult, ValidationStatus,
    ExceptionType, SAMPLE_PURCHASE_ORDERS
)
from ..utils.config import get_settings, VALIDATION_RULES


class ValidationAgent(BaseAgent):
    """
    Business Rules Validation Agent.

    Implements enterprise P2P validation logic:
    - Field completeness
    - Amount validation
    - Date validation
    - Vendor verification (against approved vendor list)
    - Duplicate detection
    - Purchase Order matching
    """

    def __init__(self):
        super().__init__(
            name="InvoiceValidationAgent",
            role=AgentRole.VALIDATOR
        )
        self.settings = get_settings()
        self._processed_invoices: List[Dict] = []  # Simulated database
        self._register_tools()

    def _register_tools(self):
        """Register validation tools."""

        self.register_tool(Tool(
            name="validate_required_fields",
            description="Check if all required invoice fields are present and valid",
            parameters={
                "invoice_data": {
                    "type": "object",
                    "description": "Invoice data to validate"
                }
            },
            function=self._validate_required_fields,
            required_params=["invoice_data"]
        ))

        self.register_tool(Tool(
            name="validate_amounts",
            description="Validate invoice amounts (subtotal, tax, total calculations)",
            parameters={
                "invoice_data": {
                    "type": "object",
                    "description": "Invoice data to validate"
                }
            },
            function=self._validate_amounts,
            required_params=["invoice_data"]
        ))

        self.register_tool(Tool(
            name="validate_dates",
            description="Validate invoice dates are reasonable and not in future",
            parameters={
                "invoice_date": {
                    "type": "string",
                    "description": "Invoice date"
                },
                "due_date": {
                    "type": "string",
                    "description": "Due date (optional)"
                }
            },
            function=self._validate_dates,
            required_params=["invoice_date"]
        ))

        self.register_tool(Tool(
            name="verify_vendor",
            description="Check if vendor is in approved vendor list",
            parameters={
                "vendor_name": {
                    "type": "string",
                    "description": "Vendor name to verify"
                }
            },
            function=self._verify_vendor,
            required_params=["vendor_name"]
        ))

        self.register_tool(Tool(
            name="check_duplicate",
            description="Check if this invoice might be a duplicate",
            parameters={
                "vendor_name": {
                    "type": "string",
                    "description": "Vendor name"
                },
                "invoice_number": {
                    "type": "string",
                    "description": "Invoice number"
                },
                "amount": {
                    "type": "number",
                    "description": "Invoice amount"
                }
            },
            function=self._check_duplicate,
            required_params=["vendor_name", "invoice_number", "amount"]
        ))

        self.register_tool(Tool(
            name="match_purchase_order",
            description="Match invoice to existing Purchase Order (3-way match)",
            parameters={
                "po_number": {
                    "type": "string",
                    "description": "PO number from invoice"
                },
                "vendor_name": {
                    "type": "string",
                    "description": "Vendor name"
                },
                "amount": {
                    "type": "number",
                    "description": "Invoice amount"
                }
            },
            function=self._match_purchase_order,
            required_params=["vendor_name", "amount"]
        ))

    async def _validate_required_fields(self, invoice_data: Dict) -> ValidationResult:
        """Validate all required fields are present."""
        missing = []
        required = VALIDATION_RULES["required_fields"]

        for field in required:
            value = invoice_data.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field)

        if missing:
            return ValidationResult(
                rule_name="required_fields",
                status=ValidationStatus.FAILED,
                message=f"Missing required fields: {', '.join(missing)}",
                details={"missing_fields": missing}
            )

        return ValidationResult(
            rule_name="required_fields",
            status=ValidationStatus.PASSED,
            message="All required fields present",
            details={"fields_checked": required}
        )

    async def _validate_amounts(self, invoice_data: Dict) -> ValidationResult:
        """Validate invoice amounts."""
        total = invoice_data.get("total_amount", 0)
        subtotal = invoice_data.get("subtotal", 0)
        tax = invoice_data.get("tax_amount", 0)

        rules = VALIDATION_RULES["amount_validation"]
        issues = []

        # Check min/max
        if total < rules["min_amount"]:
            issues.append(f"Total amount {total} below minimum {rules['min_amount']}")
        if total > rules["max_amount"]:
            issues.append(f"Total amount {total} exceeds maximum {rules['max_amount']}")

        # Check calculation (with tolerance)
        if subtotal > 0:
            expected_total = subtotal + tax
            tolerance = total * self.settings.TOLERANCE_PERCENTAGE
            if abs(total - expected_total) > tolerance:
                issues.append(
                    f"Amount mismatch: subtotal({subtotal}) + tax({tax}) = {expected_total}, "
                    f"but total is {total}"
                )

        if issues:
            return ValidationResult(
                rule_name="amount_validation",
                status=ValidationStatus.WARNING if len(issues) == 1 else ValidationStatus.FAILED,
                message="; ".join(issues),
                details={"total": total, "subtotal": subtotal, "tax": tax}
            )

        return ValidationResult(
            rule_name="amount_validation",
            status=ValidationStatus.PASSED,
            message="Amount validation passed",
            details={"total": total, "subtotal": subtotal, "tax": tax}
        )

    async def _validate_dates(self, invoice_date: str, due_date: str = None) -> ValidationResult:
        """Validate invoice dates."""
        issues = []
        today = date.today()
        rules = VALIDATION_RULES["date_validation"]

        # Parse invoice date
        try:
            if isinstance(invoice_date, str):
                inv_date = datetime.fromisoformat(invoice_date).date()
            else:
                inv_date = invoice_date
        except:
            return ValidationResult(
                rule_name="date_validation",
                status=ValidationStatus.FAILED,
                message=f"Cannot parse invoice date: {invoice_date}",
                details={}
            )

        # Check if future date
        if inv_date > today and not rules["future_date_allowed"]:
            issues.append(f"Invoice date {inv_date} is in the future")

        # Check if too old
        max_age = timedelta(days=rules["max_age_days"])
        if (today - inv_date) > max_age:
            issues.append(f"Invoice date {inv_date} is older than {rules['max_age_days']} days")

        # Check due date if present
        if due_date:
            try:
                if isinstance(due_date, str):
                    d_date = datetime.fromisoformat(due_date).date()
                else:
                    d_date = due_date
                if d_date < inv_date:
                    issues.append("Due date is before invoice date")
            except:
                pass  # Due date parsing failed, not critical

        if issues:
            return ValidationResult(
                rule_name="date_validation",
                status=ValidationStatus.FAILED,
                message="; ".join(issues),
                details={"invoice_date": str(invoice_date), "due_date": str(due_date)}
            )

        return ValidationResult(
            rule_name="date_validation",
            status=ValidationStatus.PASSED,
            message="Date validation passed",
            details={"invoice_date": str(invoice_date)}
        )

    async def _verify_vendor(self, vendor_name: str) -> ValidationResult:
        """Check if vendor is approved."""
        approved_vendors = self.settings.APPROVED_VENDORS

        # Fuzzy matching - check if vendor name contains approved vendor
        vendor_lower = vendor_name.lower()
        is_approved = any(
            approved.lower() in vendor_lower or vendor_lower in approved.lower()
            for approved in approved_vendors
        )

        if is_approved:
            return ValidationResult(
                rule_name="vendor_verification",
                status=ValidationStatus.PASSED,
                message=f"Vendor '{vendor_name}' is approved",
                details={"vendor_name": vendor_name, "approved": True}
            )

        return ValidationResult(
            rule_name="vendor_verification",
            status=ValidationStatus.WARNING,
            message=f"Vendor '{vendor_name}' not found in approved vendor list",
            details={
                "vendor_name": vendor_name,
                "approved": False,
                "requires_action": "vendor_management_review"
            }
        )

    async def _check_duplicate(self, vendor_name: str, invoice_number: str,
                               amount: float) -> ValidationResult:
        """Check for potential duplicate invoices."""
        # In production, this would query the database
        # Simulating with in-memory list
        for processed in self._processed_invoices:
            if (processed["vendor_name"].lower() == vendor_name.lower() and
                processed["invoice_number"].lower() == invoice_number.lower()):
                return ValidationResult(
                    rule_name="duplicate_check",
                    status=ValidationStatus.FAILED,
                    message=f"Duplicate invoice detected: {invoice_number} from {vendor_name}",
                    details={
                        "original_id": processed.get("id"),
                        "is_duplicate": True
                    }
                )

            # Also check for similar amounts from same vendor
            if (processed["vendor_name"].lower() == vendor_name.lower() and
                abs(processed["amount"] - amount) < 0.01):
                return ValidationResult(
                    rule_name="duplicate_check",
                    status=ValidationStatus.WARNING,
                    message=f"Potential duplicate: Same vendor and amount found",
                    details={
                        "original_id": processed.get("id"),
                        "potential_duplicate": True
                    }
                )

        return ValidationResult(
            rule_name="duplicate_check",
            status=ValidationStatus.PASSED,
            message="No duplicate detected",
            details={"is_duplicate": False}
        )

    async def _match_purchase_order(self, vendor_name: str, amount: float,
                                    po_number: str = None) -> ValidationResult:
        """
        Perform 3-way match: Invoice <-> PO <-> Receipt.

        For demo, we match against sample PO data.
        """
        # Search for matching PO
        matching_po = None

        for po in SAMPLE_PURCHASE_ORDERS:
            # If PO number provided, try exact match
            if po_number and po.po_number.lower() == po_number.lower():
                matching_po = po
                break

            # Otherwise match by vendor and similar amount
            if po.vendor_name.lower() in vendor_name.lower() or vendor_name.lower() in po.vendor_name.lower():
                tolerance = po.total_amount * self.settings.TOLERANCE_PERCENTAGE
                if abs(po.total_amount - amount) <= tolerance:
                    matching_po = po
                    break

        if matching_po:
            amount_match = abs(matching_po.total_amount - amount) <= (matching_po.total_amount * 0.02)
            return ValidationResult(
                rule_name="po_matching",
                status=ValidationStatus.PASSED if amount_match else ValidationStatus.WARNING,
                message=f"Matched to PO {matching_po.po_number}" +
                        (f" (amount variance detected)" if not amount_match else ""),
                details={
                    "po_number": matching_po.po_number,
                    "po_amount": matching_po.total_amount,
                    "invoice_amount": amount,
                    "variance": amount - matching_po.total_amount,
                    "matched": True
                }
            )

        # No PO match found
        if po_number:
            return ValidationResult(
                rule_name="po_matching",
                status=ValidationStatus.FAILED,
                message=f"PO {po_number} not found in system",
                details={"po_number": po_number, "matched": False}
            )

        return ValidationResult(
            rule_name="po_matching",
            status=ValidationStatus.WARNING,
            message="No PO reference provided - requires manual verification",
            details={"matched": False, "requires_action": "procurement_review"}
        )

    def get_system_prompt(self) -> str:
        return """You are an Invoice Validation Agent responsible for ensuring data quality and compliance.

Your validation checks:
1. Required fields are complete
2. Amounts are calculated correctly
3. Dates are valid and reasonable
4. Vendor is in approved list
5. No duplicate invoices
6. Invoice matches Purchase Order (3-way match)

Flag any issues and determine if invoice can proceed or needs exception handling."""

    async def run(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Execute validation workflow."""
        start_time = datetime.now()
        tools_used = []
        self.clear_history()

        invoice_data = input_data.get("invoice_data")
        if not invoice_data:
            return AgentResponse(
                success=False,
                result=None,
                thoughts=[],
                tools_used=[],
                execution_time_ms=0,
                error="No invoice data provided for validation"
            )

        validation_results = []
        exceptions = []

        try:
            # Step 1: Validate required fields
            self.record_thought(
                observation="Received invoice data for validation",
                reasoning="First check if all required fields are present",
                action="validate_required_fields",
                action_input={"invoice_data": "..."}
            )

            result = await self.execute_tool("validate_required_fields", invoice_data=invoice_data)
            validation_results.append(result)
            tools_used.append("validate_required_fields")

            if result.status == ValidationStatus.FAILED:
                exceptions.append(ExceptionType.INVALID_DATA)

            # Step 2: Validate amounts
            self.record_thought(
                observation=f"Required fields check: {result.status.value}",
                reasoning="Now validate the financial amounts",
                action="validate_amounts",
                action_input={"invoice_data": "..."}
            )

            result = await self.execute_tool("validate_amounts", invoice_data=invoice_data)
            validation_results.append(result)
            tools_used.append("validate_amounts")

            if result.status == ValidationStatus.FAILED:
                exceptions.append(ExceptionType.AMOUNT_MISMATCH)

            # Step 3: Validate dates
            invoice_date = invoice_data.get("invoice_date", str(date.today()))
            due_date = invoice_data.get("due_date")

            self.record_thought(
                observation=f"Amount validation: {result.status.value}",
                reasoning="Check if invoice dates are valid",
                action="validate_dates",
                action_input={"invoice_date": invoice_date}
            )

            result = await self.execute_tool(
                "validate_dates",
                invoice_date=invoice_date,
                due_date=due_date
            )
            validation_results.append(result)
            tools_used.append("validate_dates")

            # Step 4: Verify vendor
            vendor_name = invoice_data.get("vendor_name", "")

            self.record_thought(
                observation=f"Date validation: {result.status.value}",
                reasoning="Verify the vendor is in our approved vendor list",
                action="verify_vendor",
                action_input={"vendor_name": vendor_name}
            )

            result = await self.execute_tool("verify_vendor", vendor_name=vendor_name)
            validation_results.append(result)
            tools_used.append("verify_vendor")

            if result.status == ValidationStatus.FAILED:
                exceptions.append(ExceptionType.VENDOR_NOT_APPROVED)

            # Step 5: Check for duplicates
            invoice_number = invoice_data.get("invoice_number", "")
            amount = invoice_data.get("total_amount", 0)

            self.record_thought(
                observation=f"Vendor verification: {result.status.value}",
                reasoning="Check if this might be a duplicate invoice",
                action="check_duplicate",
                action_input={"vendor_name": vendor_name, "invoice_number": invoice_number}
            )

            result = await self.execute_tool(
                "check_duplicate",
                vendor_name=vendor_name,
                invoice_number=invoice_number,
                amount=amount
            )
            validation_results.append(result)
            tools_used.append("check_duplicate")

            if result.status == ValidationStatus.FAILED:
                exceptions.append(ExceptionType.DUPLICATE_SUSPECTED)

            # Step 6: PO Matching
            po_number = invoice_data.get("po_number")

            self.record_thought(
                observation=f"Duplicate check: {result.status.value}",
                reasoning="Attempt to match invoice to a Purchase Order",
                action="match_purchase_order",
                action_input={"po_number": po_number, "vendor_name": vendor_name}
            )

            result = await self.execute_tool(
                "match_purchase_order",
                po_number=po_number,
                vendor_name=vendor_name,
                amount=amount
            )
            validation_results.append(result)
            tools_used.append("match_purchase_order")

            if result.status == ValidationStatus.FAILED:
                exceptions.append(ExceptionType.MISSING_PO)

            # Determine overall status
            statuses = [r.status for r in validation_results]
            if ValidationStatus.FAILED in statuses:
                overall_status = ValidationStatus.FAILED
            elif ValidationStatus.WARNING in statuses:
                overall_status = ValidationStatus.WARNING
            else:
                overall_status = ValidationStatus.PASSED

            self.record_thought(
                observation=f"All validations complete. Status: {overall_status.value}",
                reasoning=f"Found {len(exceptions)} exceptions. Returning validation results.",
                action="return_results",
                action_input={}
            )

            return AgentResponse(
                success=overall_status != ValidationStatus.FAILED,
                result={
                    "overall_status": overall_status.value,
                    "validation_results": [r.model_dump() for r in validation_results],
                    "exceptions": [e.value for e in exceptions],
                    "can_auto_process": overall_status == ValidationStatus.PASSED
                },
                thoughts=self.thought_history,
                tools_used=tools_used,
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )

        except Exception as e:
            return AgentResponse(
                success=False,
                result=None,
                thoughts=self.thought_history,
                tools_used=tools_used,
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                error=str(e)
            )

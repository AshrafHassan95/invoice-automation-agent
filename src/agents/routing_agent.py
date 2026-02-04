"""
Routing Agent for Invoice Approval Workflow.

This agent determines the appropriate approval routing based on:
1. Invoice amount thresholds
2. Validation results
3. Exception types
4. Business rules
"""
from typing import Dict, Any, List
from datetime import datetime, timedelta

from .base_agent import BaseAgent, AgentRole, Tool, AgentResponse
from ..models.invoice import ApprovalLevel, ExceptionType, ValidationStatus
from ..utils.config import get_settings, ROUTING_RULES


class RoutingAgent(BaseAgent):
    """
    Intelligent Routing Agent for invoice approval workflow.

    Determines:
    - Which approval level is required
    - Who should review exceptions
    - Priority of processing
    - SLA deadlines
    """

    def __init__(self):
        super().__init__(
            name="InvoiceRoutingAgent",
            role=AgentRole.ROUTER
        )
        self.settings = get_settings()
        self._register_tools()

    def _register_tools(self):
        """Register routing tools."""

        self.register_tool(Tool(
            name="determine_approval_level",
            description="Determine required approval level based on invoice amount",
            parameters={
                "amount": {
                    "type": "number",
                    "description": "Invoice total amount"
                },
                "currency": {
                    "type": "string",
                    "description": "Currency code"
                }
            },
            function=self._determine_approval_level,
            required_params=["amount"]
        ))

        self.register_tool(Tool(
            name="check_auto_approval_eligibility",
            description="Check if invoice qualifies for automatic approval",
            parameters={
                "amount": {
                    "type": "number",
                    "description": "Invoice amount"
                },
                "validation_status": {
                    "type": "string",
                    "description": "Overall validation status"
                },
                "has_po_match": {
                    "type": "boolean",
                    "description": "Whether invoice matches a PO"
                },
                "vendor_approved": {
                    "type": "boolean",
                    "description": "Whether vendor is approved"
                }
            },
            function=self._check_auto_approval_eligibility,
            required_params=["amount", "validation_status"]
        ))

        self.register_tool(Tool(
            name="route_exception",
            description="Route exception to appropriate handler",
            parameters={
                "exception_type": {
                    "type": "string",
                    "description": "Type of exception"
                }
            },
            function=self._route_exception,
            required_params=["exception_type"]
        ))

        self.register_tool(Tool(
            name="calculate_sla",
            description="Calculate SLA deadline based on priority and amount",
            parameters={
                "amount": {
                    "type": "number",
                    "description": "Invoice amount"
                },
                "has_discount": {
                    "type": "boolean",
                    "description": "Whether early payment discount applies"
                },
                "due_date": {
                    "type": "string",
                    "description": "Invoice due date"
                }
            },
            function=self._calculate_sla,
            required_params=["amount"]
        ))

        self.register_tool(Tool(
            name="assign_approver",
            description="Assign specific approver based on rules",
            parameters={
                "approval_level": {
                    "type": "string",
                    "description": "Required approval level"
                },
                "department": {
                    "type": "string",
                    "description": "Requesting department"
                },
                "amount": {
                    "type": "number",
                    "description": "Invoice amount"
                }
            },
            function=self._assign_approver,
            required_params=["approval_level"]
        ))

        self.register_tool(Tool(
            name="create_approval_request",
            description="Create the final approval request with all routing details",
            parameters={
                "invoice_data": {
                    "type": "object",
                    "description": "Invoice data"
                },
                "approval_level": {
                    "type": "string",
                    "description": "Approval level"
                },
                "approver": {
                    "type": "string",
                    "description": "Assigned approver"
                },
                "sla_deadline": {
                    "type": "string",
                    "description": "SLA deadline"
                },
                "priority": {
                    "type": "string",
                    "description": "Priority level"
                }
            },
            function=self._create_approval_request,
            required_params=["invoice_data", "approval_level"]
        ))

    async def _determine_approval_level(self, amount: float,
                                        currency: str = "USD") -> Dict[str, Any]:
        """Determine approval level based on amount thresholds."""
        rules = ROUTING_RULES

        # Convert to USD equivalent if needed (simplified)
        usd_amount = amount  # In production, use exchange rates

        if usd_amount <= rules["auto_approve"]["max_amount"]:
            level = ApprovalLevel.AUTO_APPROVED
            reason = f"Amount ${usd_amount:,.2f} within auto-approve threshold"
        elif usd_amount <= rules["manager_review"]["max_amount"]:
            level = ApprovalLevel.MANAGER
            reason = f"Amount ${usd_amount:,.2f} requires manager approval"
        elif usd_amount <= rules["director_review"]["max_amount"]:
            level = ApprovalLevel.DIRECTOR
            reason = f"Amount ${usd_amount:,.2f} requires director approval"
        else:
            level = ApprovalLevel.EXECUTIVE
            reason = f"Amount ${usd_amount:,.2f} requires executive approval"

        return {
            "approval_level": level.value,
            "reason": reason,
            "amount_usd": usd_amount,
            "threshold_used": rules
        }

    async def _check_auto_approval_eligibility(self, amount: float,
                                               validation_status: str,
                                               has_po_match: bool = False,
                                               vendor_approved: bool = False) -> Dict[str, Any]:
        """Check if invoice can be auto-approved."""
        rules = ROUTING_RULES["auto_approve"]
        eligible = True
        reasons = []

        # Check amount
        if amount > rules["max_amount"]:
            eligible = False
            reasons.append(f"Amount ${amount:,.2f} exceeds auto-approve limit ${rules['max_amount']:,.2f}")

        # Check PO requirement
        if rules["requires_po_match"] and not has_po_match:
            eligible = False
            reasons.append("PO match required for auto-approval")

        # Check vendor approval
        if rules["requires_vendor_approved"] and not vendor_approved:
            eligible = False
            reasons.append("Vendor must be pre-approved for auto-approval")

        # Check validation status
        if validation_status != "passed":
            eligible = False
            reasons.append(f"Validation status '{validation_status}' does not qualify")

        return {
            "eligible_for_auto_approval": eligible,
            "reasons": reasons if not eligible else ["All auto-approval criteria met"],
            "criteria_checked": {
                "amount_within_limit": amount <= rules["max_amount"],
                "po_matched": has_po_match,
                "vendor_approved": vendor_approved,
                "validation_passed": validation_status == "passed"
            }
        }

    async def _route_exception(self, exception_type: str) -> Dict[str, Any]:
        """Route exception to appropriate handler."""
        exception_routing = ROUTING_RULES["exception_handling"]

        handler = exception_routing.get(exception_type, "accounts_payable")

        handler_details = {
            "procurement_team": {
                "team": "Procurement",
                "email": "procurement@company.com",
                "sla_hours": 24
            },
            "vendor_management": {
                "team": "Vendor Management",
                "email": "vendors@company.com",
                "sla_hours": 48
            },
            "accounts_payable": {
                "team": "Accounts Payable",
                "email": "ap@company.com",
                "sla_hours": 24
            },
            "requester": {
                "team": "Original Requester",
                "email": None,  # Would be looked up
                "sla_hours": 48
            }
        }

        details = handler_details.get(handler, handler_details["accounts_payable"])

        return {
            "exception_type": exception_type,
            "routed_to": handler,
            "handler_details": details,
            "action_required": self._get_exception_action(exception_type)
        }

    def _get_exception_action(self, exception_type: str) -> str:
        """Get required action for exception type."""
        actions = {
            "missing_po": "Create or locate Purchase Order reference",
            "vendor_not_approved": "Submit vendor for approval or find alternative",
            "duplicate_suspected": "Verify if duplicate or mark as valid",
            "amount_mismatch": "Reconcile amount difference with requester",
            "invalid_data": "Correct invoice data or request new invoice"
        }
        return actions.get(exception_type, "Review and resolve exception")

    async def _calculate_sla(self, amount: float, has_discount: bool = False,
                            due_date: str = None) -> Dict[str, Any]:
        """Calculate SLA deadline for processing."""
        now = datetime.now()

        # Base SLA by amount
        if amount > 100000:
            base_hours = 4  # High priority
            priority = "critical"
        elif amount > 25000:
            base_hours = 8
            priority = "high"
        elif amount > 5000:
            base_hours = 24
            priority = "medium"
        else:
            base_hours = 48
            priority = "normal"

        # Adjust for early payment discount
        if has_discount:
            base_hours = min(base_hours, 4)
            priority = "critical"

        deadline = now + timedelta(hours=base_hours)

        return {
            "priority": priority,
            "sla_hours": base_hours,
            "deadline": deadline.isoformat(),
            "deadline_formatted": deadline.strftime("%Y-%m-%d %H:%M"),
            "has_early_payment_discount": has_discount
        }

    async def _assign_approver(self, approval_level: str,
                               department: str = "General",
                               amount: float = 0) -> Dict[str, Any]:
        """Assign specific approver based on rules."""
        # Simulated approver assignment
        # In production, this would query org hierarchy

        approvers = {
            "auto_approved": {
                "approver_id": "SYSTEM",
                "approver_name": "Automated Approval",
                "approver_email": "system@company.com"
            },
            "manager": {
                "approver_id": "MGR001",
                "approver_name": "John Smith",
                "approver_email": "john.smith@company.com"
            },
            "director": {
                "approver_id": "DIR001",
                "approver_name": "Sarah Johnson",
                "approver_email": "sarah.johnson@company.com"
            },
            "executive": {
                "approver_id": "EXEC001",
                "approver_name": "Michael Chen",
                "approver_email": "michael.chen@company.com"
            }
        }

        approver = approvers.get(approval_level, approvers["manager"])

        return {
            "approval_level": approval_level,
            "assigned_approver": approver,
            "backup_approver": approvers.get("director") if approval_level == "manager" else None,
            "escalation_after_hours": 24
        }

    async def _create_approval_request(self, invoice_data: Dict,
                                       approval_level: str,
                                       approver: str = None,
                                       sla_deadline: str = None,
                                       priority: str = "normal") -> Dict[str, Any]:
        """Create final approval request."""
        return {
            "request_id": f"APR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "invoice_number": invoice_data.get("invoice_number"),
            "vendor_name": invoice_data.get("vendor_name"),
            "amount": invoice_data.get("total_amount"),
            "currency": invoice_data.get("currency", "USD"),
            "approval_level": approval_level,
            "assigned_to": approver,
            "priority": priority,
            "sla_deadline": sla_deadline,
            "status": "pending_approval" if approval_level != "auto_approved" else "approved",
            "created_at": datetime.now().isoformat(),
            "workflow_actions": self._get_workflow_actions(approval_level)
        }

    def _get_workflow_actions(self, approval_level: str) -> List[str]:
        """Get available workflow actions for approval level."""
        if approval_level == "auto_approved":
            return ["create_payment_request"]
        return ["approve", "reject", "request_info", "escalate", "delegate"]

    def get_system_prompt(self) -> str:
        return """You are an Invoice Routing Agent responsible for workflow automation.

Your responsibilities:
1. Determine the appropriate approval level based on amount
2. Check if invoice qualifies for automatic approval
3. Route exceptions to the right teams
4. Calculate SLA deadlines
5. Assign appropriate approvers
6. Create the approval request

Always ensure compliance with approval thresholds and business rules."""

    async def run(self, input_data: Dict[str, Any]) -> AgentResponse:
        """Execute routing workflow."""
        start_time = datetime.now()
        tools_used = []
        self.clear_history()

        invoice_data = input_data.get("invoice_data")
        validation_result = input_data.get("validation_result", {})

        if not invoice_data:
            return AgentResponse(
                success=False,
                result=None,
                thoughts=[],
                tools_used=[],
                execution_time_ms=0,
                error="No invoice data provided for routing"
            )

        try:
            amount = invoice_data.get("total_amount", 0)
            currency = invoice_data.get("currency", "USD")
            validation_status = validation_result.get("overall_status", "pending")
            exceptions = validation_result.get("exceptions", [])

            # Check for PO match and vendor approval from validation results
            validation_details = validation_result.get("validation_results", [])
            has_po_match = any(
                v.get("rule_name") == "po_matching" and v.get("status") == "passed"
                for v in validation_details
            )
            vendor_approved = any(
                v.get("rule_name") == "vendor_verification" and v.get("status") == "passed"
                for v in validation_details
            )

            # Step 1: Check auto-approval eligibility
            self.record_thought(
                observation=f"Invoice amount: ${amount:,.2f}, Validation: {validation_status}",
                reasoning="First check if this invoice qualifies for automatic approval",
                action="check_auto_approval_eligibility",
                action_input={"amount": amount, "validation_status": validation_status}
            )

            auto_check = await self.execute_tool(
                "check_auto_approval_eligibility",
                amount=amount,
                validation_status=validation_status,
                has_po_match=has_po_match,
                vendor_approved=vendor_approved
            )
            tools_used.append("check_auto_approval_eligibility")

            # Step 2: Handle exceptions if any
            exception_routes = []
            if exceptions:
                for exc in exceptions:
                    self.record_thought(
                        observation=f"Exception found: {exc}",
                        reasoning=f"Need to route exception '{exc}' to appropriate handler",
                        action="route_exception",
                        action_input={"exception_type": exc}
                    )

                    route = await self.execute_tool("route_exception", exception_type=exc)
                    exception_routes.append(route)
                    tools_used.append("route_exception")

            # Step 3: Determine approval level
            self.record_thought(
                observation=f"Auto-approval eligible: {auto_check['eligible_for_auto_approval']}",
                reasoning="Determine the required approval level based on amount",
                action="determine_approval_level",
                action_input={"amount": amount, "currency": currency}
            )

            level_result = await self.execute_tool(
                "determine_approval_level",
                amount=amount,
                currency=currency
            )
            tools_used.append("determine_approval_level")

            approval_level = level_result["approval_level"]

            # Override to exception if there are unresolved exceptions
            if exceptions and validation_status == "failed":
                approval_level = "exception"

            # Step 4: Calculate SLA
            self.record_thought(
                observation=f"Approval level: {approval_level}",
                reasoning="Calculate SLA deadline for this invoice",
                action="calculate_sla",
                action_input={"amount": amount}
            )

            sla_result = await self.execute_tool(
                "calculate_sla",
                amount=amount,
                has_discount=False,
                due_date=invoice_data.get("due_date")
            )
            tools_used.append("calculate_sla")

            # Step 5: Assign approver
            self.record_thought(
                observation=f"SLA: {sla_result['priority']} priority, deadline: {sla_result['deadline_formatted']}",
                reasoning="Assign appropriate approver for this invoice",
                action="assign_approver",
                action_input={"approval_level": approval_level}
            )

            approver_result = await self.execute_tool(
                "assign_approver",
                approval_level=approval_level,
                amount=amount
            )
            tools_used.append("assign_approver")

            # Step 6: Create approval request
            self.record_thought(
                observation=f"Approver: {approver_result['assigned_approver']['approver_name']}",
                reasoning="Create the final approval request",
                action="create_approval_request",
                action_input={"invoice_data": "...", "approval_level": approval_level}
            )

            approval_request = await self.execute_tool(
                "create_approval_request",
                invoice_data=invoice_data,
                approval_level=approval_level,
                approver=approver_result["assigned_approver"]["approver_name"],
                sla_deadline=sla_result["deadline"],
                priority=sla_result["priority"]
            )
            tools_used.append("create_approval_request")

            # Final summary
            self.record_thought(
                observation=f"Approval request created: {approval_request['request_id']}",
                reasoning="Routing complete. Returning results.",
                action="return_results",
                action_input={}
            )

            return AgentResponse(
                success=True,
                result={
                    "approval_request": approval_request,
                    "auto_approval_check": auto_check,
                    "approval_level": approval_level,
                    "approver": approver_result,
                    "sla": sla_result,
                    "exception_routes": exception_routes,
                    "routing_summary": {
                        "invoice_number": invoice_data.get("invoice_number"),
                        "amount": amount,
                        "status": approval_request["status"],
                        "assigned_to": approval_request["assigned_to"],
                        "priority": approval_request["priority"],
                        "deadline": sla_result["deadline_formatted"]
                    }
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

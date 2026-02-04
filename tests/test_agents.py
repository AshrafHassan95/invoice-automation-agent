"""
Unit tests for Invoice Automation Agents.

Run with: pytest tests/ -v
"""
import pytest
import asyncio
from datetime import date

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.validation_agent import ValidationAgent
from src.agents.routing_agent import RoutingAgent
from src.models.invoice import ValidationStatus


class TestValidationAgent:
    """Tests for the Validation Agent."""

    @pytest.fixture
    def agent(self):
        return ValidationAgent()

    @pytest.fixture
    def valid_invoice(self):
        return {
            "vendor_name": "ACME Corporation",
            "invoice_number": "INV-2024-001",
            "invoice_date": str(date.today()),
            "total_amount": 4500.00,
            "subtotal": 4166.67,
            "tax_amount": 333.33,
            "currency": "USD",
            "po_number": "PO-2024-001"
        }

    @pytest.mark.asyncio
    async def test_validate_required_fields_pass(self, agent, valid_invoice):
        """Test that valid invoice passes required fields check."""
        result = await agent._validate_required_fields(valid_invoice)
        assert result.status == ValidationStatus.PASSED

    @pytest.mark.asyncio
    async def test_validate_required_fields_fail(self, agent):
        """Test that invoice with missing fields fails."""
        incomplete_invoice = {"vendor_name": "Test"}
        result = await agent._validate_required_fields(incomplete_invoice)
        assert result.status == ValidationStatus.FAILED
        assert "invoice_number" in result.message

    @pytest.mark.asyncio
    async def test_validate_amounts_pass(self, agent, valid_invoice):
        """Test amount validation passes for correct calculations."""
        result = await agent._validate_amounts(valid_invoice)
        assert result.status == ValidationStatus.PASSED

    @pytest.mark.asyncio
    async def test_verify_vendor_approved(self, agent):
        """Test approved vendor verification."""
        result = await agent._verify_vendor("ACME Corporation")
        assert result.status == ValidationStatus.PASSED

    @pytest.mark.asyncio
    async def test_verify_vendor_not_approved(self, agent):
        """Test unapproved vendor verification."""
        result = await agent._verify_vendor("Unknown Company XYZ")
        assert result.status == ValidationStatus.WARNING

    @pytest.mark.asyncio
    async def test_check_duplicate_no_duplicate(self, agent):
        """Test duplicate check with no duplicates."""
        result = await agent._check_duplicate(
            vendor_name="ACME Corporation",
            invoice_number="INV-NEW-001",
            amount=1000.00
        )
        assert result.status == ValidationStatus.PASSED

    @pytest.mark.asyncio
    async def test_po_matching_found(self, agent):
        """Test PO matching with matching PO."""
        result = await agent._match_purchase_order(
            po_number="PO-2024-001",
            vendor_name="ACME Corporation",
            amount=4500.00
        )
        assert result.status == ValidationStatus.PASSED

    @pytest.mark.asyncio
    async def test_po_matching_not_found(self, agent):
        """Test PO matching with no matching PO."""
        result = await agent._match_purchase_order(
            po_number="PO-INVALID-999",
            vendor_name="Unknown Vendor",
            amount=999.00
        )
        assert result.status == ValidationStatus.FAILED

    @pytest.mark.asyncio
    async def test_full_validation_run(self, agent, valid_invoice):
        """Test full validation workflow."""
        result = await agent.run({"invoice_data": valid_invoice})
        assert result.success
        assert len(result.tools_used) > 0
        assert len(result.thoughts) > 0


class TestRoutingAgent:
    """Tests for the Routing Agent."""

    @pytest.fixture
    def agent(self):
        return RoutingAgent()

    @pytest.mark.asyncio
    async def test_approval_level_auto(self, agent):
        """Test auto-approval for low amount."""
        result = await agent._determine_approval_level(amount=2000.00)
        assert result["approval_level"] == "auto_approved"

    @pytest.mark.asyncio
    async def test_approval_level_manager(self, agent):
        """Test manager approval for medium amount."""
        result = await agent._determine_approval_level(amount=15000.00)
        assert result["approval_level"] == "manager"

    @pytest.mark.asyncio
    async def test_approval_level_director(self, agent):
        """Test director approval for higher amount."""
        result = await agent._determine_approval_level(amount=50000.00)
        assert result["approval_level"] == "director"

    @pytest.mark.asyncio
    async def test_approval_level_executive(self, agent):
        """Test executive approval for high amount."""
        result = await agent._determine_approval_level(amount=150000.00)
        assert result["approval_level"] == "executive"

    @pytest.mark.asyncio
    async def test_auto_approval_eligibility_pass(self, agent):
        """Test auto-approval eligibility check."""
        result = await agent._check_auto_approval_eligibility(
            amount=3000.00,
            validation_status="passed",
            has_po_match=True,
            vendor_approved=True
        )
        assert result["eligible_for_auto_approval"] == True

    @pytest.mark.asyncio
    async def test_auto_approval_eligibility_fail_amount(self, agent):
        """Test auto-approval fails for high amount."""
        result = await agent._check_auto_approval_eligibility(
            amount=10000.00,
            validation_status="passed",
            has_po_match=True,
            vendor_approved=True
        )
        assert result["eligible_for_auto_approval"] == False

    @pytest.mark.asyncio
    async def test_exception_routing(self, agent):
        """Test exception routing."""
        result = await agent._route_exception("missing_po")
        assert result["routed_to"] == "procurement_team"

    @pytest.mark.asyncio
    async def test_sla_calculation_critical(self, agent):
        """Test SLA calculation for high amount."""
        result = await agent._calculate_sla(amount=150000.00)
        assert result["priority"] == "critical"
        assert result["sla_hours"] == 4

    @pytest.mark.asyncio
    async def test_sla_calculation_normal(self, agent):
        """Test SLA calculation for normal amount."""
        result = await agent._calculate_sla(amount=2000.00)
        assert result["priority"] == "normal"
        assert result["sla_hours"] == 48


class TestIntegration:
    """Integration tests for the full pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_auto_approve(self):
        """Test full pipeline with auto-approval scenario."""
        validation_agent = ValidationAgent()
        routing_agent = RoutingAgent()

        invoice_data = {
            "vendor_name": "ACME Corporation",
            "invoice_number": "INV-2024-TEST",
            "invoice_date": str(date.today()),
            "total_amount": 3000.00,
            "subtotal": 2777.78,
            "tax_amount": 222.22,
            "currency": "USD",
            "po_number": "PO-2024-001"
        }

        # Validation
        validation_result = await validation_agent.run({"invoice_data": invoice_data})
        assert validation_result.success

        # Routing
        routing_result = await routing_agent.run({
            "invoice_data": invoice_data,
            "validation_result": validation_result.result
        })
        assert routing_result.success
        assert routing_result.result["approval_level"] == "auto_approved"

    @pytest.mark.asyncio
    async def test_full_pipeline_exception(self):
        """Test full pipeline with exception scenario."""
        validation_agent = ValidationAgent()
        routing_agent = RoutingAgent()

        # Invoice without PO and unknown vendor
        invoice_data = {
            "vendor_name": "Unknown Vendor XYZ",
            "invoice_number": "INV-2024-EXC",
            "invoice_date": str(date.today()),
            "total_amount": 50000.00,
            "subtotal": 46296.30,
            "tax_amount": 3703.70,
            "currency": "USD"
            # No PO number
        }

        # Validation
        validation_result = await validation_agent.run({"invoice_data": invoice_data})

        # Routing
        routing_result = await routing_agent.run({
            "invoice_data": invoice_data,
            "validation_result": validation_result.result
        })

        # Should have exceptions routed
        assert len(routing_result.result.get("exception_routes", [])) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

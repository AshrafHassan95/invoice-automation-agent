"""
Main Invoice Processing Agent - The Orchestrator.

This is the central coordinator that:
1. Receives invoice processing requests
2. Orchestrates the specialized agents
3. Manages the overall workflow
4. Handles errors and exceptions
5. Reports processing results

This demonstrates enterprise Agentic AI architecture.
"""
import asyncio
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .base_agent import AgentOrchestrator, AgentRole
from .extraction_agent import ExtractionAgent
from .validation_agent import ValidationAgent
from .routing_agent import RoutingAgent
from ..models.invoice import ProcessingResult, InvoiceStatus, AgentAction


@dataclass
class ProcessingMetrics:
    """Metrics for invoice processing."""
    total_processed: int = 0
    successful: int = 0
    failed: int = 0
    auto_approved: int = 0
    manual_review: int = 0
    exceptions: int = 0
    avg_processing_time_ms: float = 0.0
    processing_times: list = field(default_factory=list)


class InvoiceProcessingAgent:
    """
    Main Invoice Processing Agent.

    This is the entry point for invoice automation. It:
    1. Accepts invoice documents
    2. Coordinates extraction, validation, and routing
    3. Tracks processing metrics
    4. Provides audit trail

    Architecture:
    ┌─────────────────────────────────────────────────────────┐
    │                 Invoice Processing Agent                 │
    │                    (Orchestrator)                        │
    ├─────────────────────────────────────────────────────────┤
    │                         │                                │
    │    ┌───────────────────┼───────────────────┐            │
    │    ▼                   ▼                   ▼            │
    │ ┌──────────┐    ┌──────────┐    ┌──────────┐           │
    │ │Extraction│───►│Validation│───►│ Routing  │           │
    │ │  Agent   │    │  Agent   │    │  Agent   │           │
    │ └──────────┘    └──────────┘    └──────────┘           │
    │    (IDP)        (Business      (Workflow               │
    │                  Rules)        Automation)              │
    └─────────────────────────────────────────────────────────┘
    """

    def __init__(self, use_database: bool = True):
        self.orchestrator = AgentOrchestrator()
        self.metrics = ProcessingMetrics()
        self._setup_agents()
        self.processing_history: list = []
        self.use_database = use_database

        # Initialize database if enabled
        self.db = None
        if self.use_database:
            try:
                from ..database.invoice_db import get_database
                self.db = get_database()
                print("Database persistence enabled")
            except Exception as e:
                print(f"Database initialization failed: {e}")
                self.db = None

    def _setup_agents(self):
        """Initialize and register all specialized agents."""
        # Create agents
        extraction_agent = ExtractionAgent()
        validation_agent = ValidationAgent()
        routing_agent = RoutingAgent()

        # Register with orchestrator
        self.orchestrator.register_agent(extraction_agent)
        self.orchestrator.register_agent(validation_agent)
        self.orchestrator.register_agent(routing_agent)

    async def process_invoice(self, document_path: str,
                              metadata: Optional[Dict] = None) -> ProcessingResult:
        """
        Process a single invoice through the complete pipeline.

        Args:
            document_path: Path to the invoice document
            metadata: Optional metadata (requester, department, etc.)

        Returns:
            ProcessingResult with complete processing details
        """
        start_time = datetime.now()
        invoice_id = str(uuid.uuid4())[:8]
        agent_actions = []

        print(f"\n{'='*60}")
        print(f"Processing Invoice: {document_path}")
        print(f"Invoice ID: {invoice_id}")
        print(f"{'='*60}\n")

        try:
            # Execute the orchestrated workflow
            result = await self.orchestrator.process_invoice(document_path, invoice_id)

            # Extract results from each stage
            extraction_result = None
            validation_result = None
            routing_result = None

            for stage in result.get("stages", []):
                if stage["stage"] == "extraction":
                    extraction_result = stage.get("result")
                    agent_actions.extend(self._format_actions(stage))
                elif stage["stage"] == "validation":
                    validation_result = stage.get("result")
                    agent_actions.extend(self._format_actions(stage))
                elif stage["stage"] == "routing":
                    routing_result = stage.get("result")
                    agent_actions.extend(self._format_actions(stage))

            # Determine final status
            if not result["success"]:
                final_status = InvoiceStatus.EXCEPTION
            elif routing_result and routing_result.get("approval_request", {}).get("status") == "approved":
                final_status = InvoiceStatus.APPROVED
            elif routing_result:
                final_status = InvoiceStatus.PENDING_APPROVAL
            else:
                final_status = InvoiceStatus.EXCEPTION

            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)

            # Update metrics
            self._update_metrics(result["success"], processing_time, final_status)

            # Create processing result
            processing_result = ProcessingResult(
                invoice_id=invoice_id,
                success=result["success"],
                status=final_status,
                invoice_data=extraction_result.get("invoice_data") if extraction_result else None,
                validation=validation_result,
                approval=routing_result.get("approval_request") if routing_result else None,
                processing_time_ms=processing_time,
                agent_actions=[a for a in agent_actions],
                errors=result.get("errors", [])
            )

            # Store in history
            record = {
                "invoice_id": invoice_id,
                "document_path": document_path,
                "result": processing_result.model_dump(),
                "timestamp": datetime.now().isoformat()
            }
            self.processing_history.append(record)

            # Save to database if enabled
            if self.db:
                try:
                    result_dict = processing_result.model_dump()
                    result_dict["document_path"] = document_path
                    result_dict["timestamp"] = datetime.now().isoformat()
                    self.db.save_invoice(result_dict)
                except Exception as e:
                    print(f"Failed to save to database: {e}")

            # Print summary
            self._print_summary(processing_result, routing_result)

            return processing_result

        except Exception as e:
            processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
            self.metrics.failed += 1
            self.metrics.total_processed += 1

            return ProcessingResult(
                invoice_id=invoice_id,
                success=False,
                status=InvoiceStatus.EXCEPTION,
                invoice_data=None,
                validation=None,
                approval=None,
                processing_time_ms=processing_time,
                agent_actions=agent_actions,
                errors=[str(e)]
            )

    async def process_batch(self, document_paths: list,
                           parallel: bool = True) -> list:
        """
        Process multiple invoices.

        Args:
            document_paths: List of document paths
            parallel: If True, process in parallel (faster)

        Returns:
            List of ProcessingResult objects
        """
        if parallel:
            tasks = [self.process_invoice(path) for path in document_paths]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return [r if not isinstance(r, Exception) else
                    ProcessingResult(
                        invoice_id="error",
                        success=False,
                        status=InvoiceStatus.EXCEPTION,
                        processing_time_ms=0,
                        errors=[str(r)]
                    )
                    for r in results]
        else:
            results = []
            for path in document_paths:
                result = await self.process_invoice(path)
                results.append(result)
            return results

    def _format_actions(self, stage: Dict) -> list:
        """Format stage thoughts into action strings."""
        actions = []
        for thought in stage.get("thoughts", []):
            actions.append(f"{stage['agent']}: {thought.get('action', 'unknown')}")
        return actions

    def _update_metrics(self, success: bool, processing_time: int,
                        status: InvoiceStatus):
        """Update processing metrics."""
        self.metrics.total_processed += 1
        self.metrics.processing_times.append(processing_time)
        self.metrics.avg_processing_time_ms = (
            sum(self.metrics.processing_times) / len(self.metrics.processing_times)
        )

        if success:
            self.metrics.successful += 1
        else:
            self.metrics.failed += 1

        if status == InvoiceStatus.APPROVED:
            self.metrics.auto_approved += 1
        elif status == InvoiceStatus.PENDING_APPROVAL:
            self.metrics.manual_review += 1
        elif status == InvoiceStatus.EXCEPTION:
            self.metrics.exceptions += 1

    def _print_summary(self, result: ProcessingResult, routing_result: Optional[Dict]):
        """Print processing summary."""
        print(f"\n{'-'*60}")
        print("PROCESSING SUMMARY")
        print(f"{'-'*60}")
        print(f"Invoice ID: {result.invoice_id}")
        print(f"Status: {result.status.value.upper()}")
        print(f"Success: {'Yes' if result.success else 'No'}")
        print(f"Processing Time: {result.processing_time_ms}ms")

        if result.invoice_data:
            data = result.invoice_data
            print(f"\nExtracted Data:")
            print(f"  Vendor: {data.get('vendor_name', 'N/A')}")
            print(f"  Invoice #: {data.get('invoice_number', 'N/A')}")
            print(f"  Amount: ${data.get('total_amount', 0):,.2f}")

        if routing_result:
            summary = routing_result.get("routing_summary", {})
            print(f"\nRouting:")
            print(f"  Approval Level: {routing_result.get('approval_level', 'N/A')}")
            print(f"  Assigned To: {summary.get('assigned_to', 'N/A')}")
            print(f"  Priority: {summary.get('priority', 'N/A')}")
            print(f"  Deadline: {summary.get('deadline', 'N/A')}")

        if result.errors:
            print(f"\nErrors: {', '.join(result.errors)}")

        print(f"\nAgent Actions: {len(result.agent_actions)} steps")
        print(f"{'-'*60}\n")

    def get_metrics(self) -> Dict[str, Any]:
        """Get current processing metrics."""
        return {
            "total_processed": self.metrics.total_processed,
            "successful": self.metrics.successful,
            "failed": self.metrics.failed,
            "success_rate": (
                f"{(self.metrics.successful / self.metrics.total_processed * 100):.1f}%"
                if self.metrics.total_processed > 0 else "N/A"
            ),
            "auto_approved": self.metrics.auto_approved,
            "manual_review": self.metrics.manual_review,
            "exceptions": self.metrics.exceptions,
            "avg_processing_time_ms": round(self.metrics.avg_processing_time_ms, 2),
            "automation_rate": (
                f"{((self.metrics.auto_approved + self.metrics.successful - self.metrics.manual_review) / max(self.metrics.total_processed, 1) * 100):.1f}%"
            )
        }

    def get_processing_history(self, limit: int = 10) -> list:
        """Get recent processing history."""
        return self.processing_history[-limit:]


# Factory function
def create_invoice_agent() -> InvoiceProcessingAgent:
    """Create and return an invoice processing agent."""
    return InvoiceProcessingAgent()

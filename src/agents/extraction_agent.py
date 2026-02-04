"""
Extraction Agent for Invoice Document Processing.

This agent is responsible for:
1. Analyzing the input document
2. Deciding the best extraction method
3. Extracting structured data
4. Validating extraction quality
"""
from typing import Dict, Any
from datetime import datetime

from .base_agent import BaseAgent, AgentRole, Tool, AgentResponse
from ..processors.document_processor import DocumentProcessor, ExtractionResult
from ..models.invoice import InvoiceData


class ExtractionAgent(BaseAgent):
    """
    Intelligent Document Processing Agent.

    Uses reasoning to:
    - Determine document type (digital PDF vs scanned)
    - Select appropriate extraction method
    - Validate extraction confidence
    - Request re-extraction if needed
    """

    def __init__(self):
        super().__init__(
            name="InvoiceExtractionAgent",
            role=AgentRole.EXTRACTOR
        )
        self.processor = DocumentProcessor()
        self._register_tools()

    def _register_tools(self):
        """Register extraction tools."""

        # Tool 1: Analyze Document
        self.register_tool(Tool(
            name="analyze_document",
            description="Analyze document to determine type and best extraction approach",
            parameters={
                "document_path": {
                    "type": "string",
                    "description": "Path to the document file"
                }
            },
            function=self._analyze_document,
            required_params=["document_path"]
        ))

        # Tool 2: Extract with OCR
        self.register_tool(Tool(
            name="extract_with_ocr",
            description="Extract text from document using OCR (for scanned documents)",
            parameters={
                "document_path": {
                    "type": "string",
                    "description": "Path to the document file"
                }
            },
            function=self._extract_with_ocr,
            required_params=["document_path"]
        ))

        # Tool 3: Extract with Text Parser
        self.register_tool(Tool(
            name="extract_with_parser",
            description="Extract text from digital PDF using text parser (faster, more accurate)",
            parameters={
                "document_path": {
                    "type": "string",
                    "description": "Path to the document file"
                }
            },
            function=self._extract_with_parser,
            required_params=["document_path"]
        ))

        # Tool 4: Parse Invoice Fields
        self.register_tool(Tool(
            name="parse_invoice_fields",
            description="Parse raw text into structured invoice data",
            parameters={
                "raw_text": {
                    "type": "string",
                    "description": "Raw extracted text from document"
                }
            },
            function=self._parse_invoice_fields,
            required_params=["raw_text"]
        ))

        # Tool 5: Validate Extraction
        self.register_tool(Tool(
            name="validate_extraction",
            description="Validate extracted data meets minimum quality threshold",
            parameters={
                "invoice_data": {
                    "type": "object",
                    "description": "Extracted invoice data"
                },
                "confidence": {
                    "type": "number",
                    "description": "Extraction confidence score"
                }
            },
            function=self._validate_extraction,
            required_params=["invoice_data", "confidence"]
        ))

    async def _analyze_document(self, document_path: str) -> Dict[str, Any]:
        """Analyze document to determine extraction strategy."""
        from pathlib import Path

        path = Path(document_path)
        suffix = path.suffix.lower()

        analysis = {
            "file_exists": path.exists(),
            "file_type": suffix,
            "file_size_kb": path.stat().st_size / 1024 if path.exists() else 0,
            "is_pdf": suffix == ".pdf",
            "is_image": suffix in [".png", ".jpg", ".jpeg", ".tiff"],
            "recommended_method": "parser" if suffix == ".pdf" else "ocr"
        }

        return analysis

    async def _extract_with_ocr(self, document_path: str) -> Dict[str, Any]:
        """Extract using OCR."""
        result = await self.processor.process_document(document_path)
        return {
            "success": result.success,
            "raw_text": result.raw_text,
            "confidence": result.confidence,
            "method": "ocr"
        }

    async def _extract_with_parser(self, document_path: str) -> Dict[str, Any]:
        """Extract using PDF text parser."""
        result = await self.processor.process_document(document_path)
        return {
            "success": result.success,
            "raw_text": result.raw_text,
            "confidence": result.confidence,
            "method": "parser"
        }

    async def _parse_invoice_fields(self, raw_text: str) -> Dict[str, Any]:
        """Parse raw text into structured invoice fields."""
        invoice_data, confidence = self.processor._extract_invoice_fields(raw_text)

        if invoice_data:
            return {
                "success": True,
                "invoice_data": invoice_data.model_dump(),
                "confidence": confidence
            }
        return {
            "success": False,
            "invoice_data": None,
            "confidence": 0.0
        }

    async def _validate_extraction(self, invoice_data: Dict, confidence: float) -> Dict[str, Any]:
        """Validate extraction quality."""
        issues = []

        # Check required fields
        required = ["vendor_name", "invoice_number", "total_amount"]
        for field in required:
            if not invoice_data.get(field):
                issues.append(f"Missing required field: {field}")

        # Check confidence threshold
        if confidence < 0.6:
            issues.append(f"Low confidence score: {confidence:.2f}")

        # Check amount validity
        amount = invoice_data.get("total_amount", 0)
        if amount <= 0:
            issues.append("Invalid total amount")

        return {
            "is_valid": len(issues) == 0,
            "confidence": confidence,
            "issues": issues
        }

    def get_system_prompt(self) -> str:
        return """You are an Invoice Extraction Agent specialized in Intelligent Document Processing (IDP).

Your task is to extract structured data from invoice documents accurately.

Process:
1. First, analyze the document to understand its type
2. Choose the appropriate extraction method (OCR for scanned, parser for digital)
3. Extract the raw text
4. Parse the text into structured invoice fields
5. Validate the extraction quality

Always aim for high confidence extraction. If confidence is low, consider alternative methods."""

    async def run(self, input_data: Dict[str, Any]) -> AgentResponse:
        """
        Execute the extraction workflow using ReAct pattern.

        ReAct = Reasoning + Acting:
        - Observe: Look at the document
        - Think: Decide best extraction approach
        - Act: Execute extraction tools
        - Observe: Check results
        - Repeat if needed
        """
        start_time = datetime.now()
        tools_used = []
        self.clear_history()

        document_path = input_data.get("document_path")
        if not document_path:
            return AgentResponse(
                success=False,
                result=None,
                thoughts=[],
                tools_used=[],
                execution_time_ms=0,
                error="No document path provided"
            )

        try:
            # Step 1: Analyze document
            self.record_thought(
                observation=f"Received document: {document_path}",
                reasoning="First, I need to analyze the document to determine the best extraction approach",
                action="analyze_document",
                action_input={"document_path": document_path}
            )

            analysis = await self.execute_tool("analyze_document", document_path=document_path)
            tools_used.append("analyze_document")

            if not analysis["file_exists"]:
                return AgentResponse(
                    success=False,
                    result=None,
                    thoughts=self.thought_history,
                    tools_used=tools_used,
                    execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                    error="Document file not found"
                )

            # Step 2: Choose and execute extraction method
            extraction_method = analysis["recommended_method"]

            self.record_thought(
                observation=f"Document analysis: {analysis}",
                reasoning=f"Document is {'a PDF' if analysis['is_pdf'] else 'an image'}. "
                          f"Will use {extraction_method} method for extraction.",
                action=f"extract_with_{extraction_method}",
                action_input={"document_path": document_path}
            )

            if extraction_method == "parser":
                extraction = await self.execute_tool("extract_with_parser", document_path=document_path)
                tools_used.append("extract_with_parser")
            else:
                extraction = await self.execute_tool("extract_with_ocr", document_path=document_path)
                tools_used.append("extract_with_ocr")

            if not extraction["success"] or not extraction["raw_text"]:
                # Try alternative method
                self.record_thought(
                    observation=f"Primary extraction failed or returned empty text",
                    reasoning="Will try OCR as fallback",
                    action="extract_with_ocr",
                    action_input={"document_path": document_path}
                )
                extraction = await self.execute_tool("extract_with_ocr", document_path=document_path)
                tools_used.append("extract_with_ocr")

            # Step 3: Parse invoice fields
            self.record_thought(
                observation=f"Extracted {len(extraction['raw_text'])} characters of text",
                reasoning="Now I'll parse the raw text into structured invoice fields",
                action="parse_invoice_fields",
                action_input={"raw_text": "...text content..."}
            )

            parsed = await self.execute_tool("parse_invoice_fields", raw_text=extraction["raw_text"])
            tools_used.append("parse_invoice_fields")

            if not parsed["success"]:
                return AgentResponse(
                    success=False,
                    result=None,
                    thoughts=self.thought_history,
                    tools_used=tools_used,
                    execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                    error="Failed to parse invoice fields from extracted text"
                )

            # Step 4: Validate extraction
            self.record_thought(
                observation=f"Parsed invoice data with confidence: {parsed['confidence']:.2f}",
                reasoning="Need to validate the extraction quality before proceeding",
                action="validate_extraction",
                action_input={"invoice_data": "...", "confidence": parsed["confidence"]}
            )

            validation = await self.execute_tool(
                "validate_extraction",
                invoice_data=parsed["invoice_data"],
                confidence=parsed["confidence"]
            )
            tools_used.append("validate_extraction")

            # Final thought
            self.record_thought(
                observation=f"Validation result: {validation}",
                reasoning="Extraction complete. Returning results.",
                action="return_result",
                action_input={}
            )

            return AgentResponse(
                success=validation["is_valid"],
                result={
                    "invoice_data": parsed["invoice_data"],
                    "confidence": parsed["confidence"],
                    "validation": validation,
                    "extraction_method": extraction["method"]
                },
                thoughts=self.thought_history,
                tools_used=tools_used,
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                error=None if validation["is_valid"] else f"Validation issues: {validation['issues']}"
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

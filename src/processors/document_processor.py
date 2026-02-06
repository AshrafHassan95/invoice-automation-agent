"""
Document Processor for Invoice Extraction.
Handles PDF/Image processing and OCR for Intelligent Document Processing (IDP).

This module demonstrates IDP capabilities similar to platforms like:
- Azure Document Intelligence
- ABBYY
- Kofax

For production, integrate with Azure Document Intelligence API.
"""
import re
import json
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, date
from dataclasses import dataclass

# PDF Processing
try:
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# Image Processing
try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

from ..models.invoice import InvoiceData, LineItem, Currency
from ..utils.config import get_settings


@dataclass
class ExtractionResult:
    """Result of document extraction process."""
    success: bool
    raw_text: str
    invoice_data: Optional[InvoiceData]
    confidence: float
    extraction_method: str
    errors: list


class DocumentProcessor:
    """
    Intelligent Document Processor for invoices.

    Extracts structured data from unstructured invoice documents using:
    1. PDF text extraction
    2. OCR for scanned documents/images
    3. Pattern matching for field extraction
    4. AI-powered extraction (when LLM is available)
    """

    def __init__(self):
        self.settings = get_settings()
        self._patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[str, re.Pattern]:
        """Compile regex patterns for invoice field extraction."""
        return {
            # Invoice number patterns
            "invoice_number": re.compile(
                r"(?:invoice\s*(?:#|no\.?|number)\s*:?\s*)([A-Z0-9][-A-Z0-9]{2,20})",
                re.IGNORECASE
            ),
            # Date patterns (various formats)
            "date": re.compile(
                r"(?:date(?:\s+of\s+issue)?:?\s*)(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|"
                r"\w+\s+\d{1,2},?\s+\d{4})",
                re.IGNORECASE
            ),
            # Amount patterns
            "amount": re.compile(
                r"(?:total|amount\s*due|grand\s*total|balance\s*due):?\s*"
                r"[$€£]?\s*([\d,]+\.?\d{0,2})",
                re.IGNORECASE
            ),
            # Subtotal
            "subtotal": re.compile(
                r"(?:subtotal|sub-total|sub\s+total):?\s*[$€£]?\s*([\d,]+\.?\d{0,2})",
                re.IGNORECASE
            ),
            # Tax
            "tax": re.compile(
                r"(?:tax|vat|gst|sales\s*tax):?\s*[$€£]?\s*([\d,]+\.?\d{0,2})",
                re.IGNORECASE
            ),
            # PO Number
            "po_number": re.compile(
                r"(?:p\.?o\.?\s*(?:#|no\.?|number)?:?\s*)([A-Z0-9][-A-Z0-9]{2,20})",
                re.IGNORECASE
            ),
            # Vendor/Company name (at start of document)
            "vendor_name": re.compile(
                r"^([A-Z][A-Za-z\s&,]+(?:Inc\.?|LLC|LLP|Ltd\.?|Corp\.?|Corporation|Company|Co\.?|PBC|L\.?L\.?C\.?|P\.?L\.?C\.?))",
                re.MULTILINE
            ),
            # Currency
            "currency": re.compile(
                r"(USD|EUR|GBP|MYR|SGD|\$|€|£|RM)",
                re.IGNORECASE
            ),
            # Due date
            "due_date": re.compile(
                r"(?:due\s*date|payment\s*due|pay\s*by):?\s*"
                r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|"
                r"\w+\s+\d{1,2},?\s+\d{4})",
                re.IGNORECASE
            ),
            # Payment terms
            "payment_terms": re.compile(
                r"(?:terms|payment\s*terms):?\s*(NET\s*\d+|DUE\s*ON\s*RECEIPT|\d+\s*DAYS)",
                re.IGNORECASE
            ),
        }

    async def process_document(self, file_path: str) -> ExtractionResult:
        """
        Main entry point for document processing.

        Args:
            file_path: Path to the invoice document (PDF or image)

        Returns:
            ExtractionResult with extracted data and confidence score
        """
        path = Path(file_path)

        if not path.exists():
            return ExtractionResult(
                success=False,
                raw_text="",
                invoice_data=None,
                confidence=0.0,
                extraction_method="none",
                errors=[f"File not found: {file_path}"]
            )

        # Determine extraction method based on file type
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return await self._process_pdf(path)
        elif suffix in [".png", ".jpg", ".jpeg", ".tiff"]:
            return await self._process_image(path)
        else:
            return ExtractionResult(
                success=False,
                raw_text="",
                invoice_data=None,
                confidence=0.0,
                extraction_method="none",
                errors=[f"Unsupported file format: {suffix}"]
            )

    async def _process_pdf(self, path: Path) -> ExtractionResult:
        """Extract text and data from PDF invoice."""
        errors = []
        raw_text = ""

        if not PDF_AVAILABLE:
            return ExtractionResult(
                success=False,
                raw_text="",
                invoice_data=None,
                confidence=0.0,
                extraction_method="pdf",
                errors=["PyPDF2 not installed. Run: pip install pypdf2"]
            )

        try:
            reader = PdfReader(str(path))
            text_parts = []

            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

            raw_text = "\n".join(text_parts)

            # If PDF has no extractable text, it might be scanned
            if not raw_text.strip():
                if OCR_AVAILABLE:
                    # Fall back to OCR
                    return await self._process_scanned_pdf(path)
                else:
                    errors.append("PDF appears to be scanned but OCR is not available")

        except Exception as e:
            errors.append(f"PDF extraction error: {str(e)}")
            return ExtractionResult(
                success=False,
                raw_text="",
                invoice_data=None,
                confidence=0.0,
                extraction_method="pdf",
                errors=errors
            )

        # Extract structured data from text
        invoice_data, confidence = self._extract_invoice_fields(raw_text)

        return ExtractionResult(
            success=invoice_data is not None,
            raw_text=raw_text,
            invoice_data=invoice_data,
            confidence=confidence,
            extraction_method="pdf_text",
            errors=errors
        )

    async def _process_image(self, path: Path) -> ExtractionResult:
        """Process image invoice using OCR."""
        if not OCR_AVAILABLE:
            return ExtractionResult(
                success=False,
                raw_text="",
                invoice_data=None,
                confidence=0.0,
                extraction_method="ocr",
                errors=["pytesseract/PIL not installed"]
            )

        try:
            image = Image.open(str(path))
            raw_text = pytesseract.image_to_string(image)

            invoice_data, confidence = self._extract_invoice_fields(raw_text)

            return ExtractionResult(
                success=invoice_data is not None,
                raw_text=raw_text,
                invoice_data=invoice_data,
                confidence=confidence * 0.9,  # Slightly lower confidence for OCR
                extraction_method="ocr",
                errors=[]
            )
        except Exception as e:
            return ExtractionResult(
                success=False,
                raw_text="",
                invoice_data=None,
                confidence=0.0,
                extraction_method="ocr",
                errors=[f"OCR error: {str(e)}"]
            )

    async def _process_scanned_pdf(self, path: Path) -> ExtractionResult:
        """Process scanned PDF by converting to images and running OCR."""
        try:
            from pdf2image import convert_from_path

            images = convert_from_path(str(path))
            text_parts = []

            for image in images:
                text = pytesseract.image_to_string(image)
                text_parts.append(text)

            raw_text = "\n".join(text_parts)
            invoice_data, confidence = self._extract_invoice_fields(raw_text)

            return ExtractionResult(
                success=invoice_data is not None,
                raw_text=raw_text,
                invoice_data=invoice_data,
                confidence=confidence * 0.85,  # Lower confidence for scanned PDFs
                extraction_method="pdf_ocr",
                errors=[]
            )
        except Exception as e:
            return ExtractionResult(
                success=False,
                raw_text="",
                invoice_data=None,
                confidence=0.0,
                extraction_method="pdf_ocr",
                errors=[f"Scanned PDF processing error: {str(e)}"]
            )

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text extracted from PDFs that have character spacing issues.

        Some PDFs extract with spaces between every character.
        This method attempts to fix that while preserving legitimate spaces.
        """
        # Check if text has the characteristic spacing issue
        # (spaces between most characters)
        space_ratio = text.count(' ') / max(len(text), 1)

        if space_ratio > 0.3:  # More than 30% spaces suggests spacing issue
            # Strategy: In spaced text, multiple spaces indicate word boundaries
            # Single spaces are character separators
            import re

            # Replace 2+ spaces with a placeholder to preserve word boundaries
            WORD_BOUNDARY = "<<<SPACE>>>"
            normalized = re.sub(r'\s{2,}', WORD_BOUNDARY, text)

            # Remove all remaining single spaces (character separators)
            normalized = normalized.replace(' ', '')

            # Restore word boundaries as single spaces
            normalized = normalized.replace(WORD_BOUNDARY, ' ')

            return normalized.strip()

        return text

    def _extract_invoice_fields(self, text: str) -> Tuple[Optional[InvoiceData], float]:
        """
        Extract invoice fields from raw text using pattern matching.

        Returns tuple of (InvoiceData, confidence_score)
        """
        if not text.strip():
            return None, 0.0

        # Normalize text to handle character spacing issues
        text = self._normalize_text(text)

        extracted = {}
        confidence_scores = []

        # Prioritize required fields for faster extraction
        required_fields = ["invoice_number", "date", "amount", "vendor_name"]
        optional_fields = [f for f in self._patterns.keys() if f not in required_fields]

        # Extract required fields first
        for field_name in required_fields:
            pattern = self._patterns[field_name]
            match = pattern.search(text)
            if match:
                extracted[field_name] = match.group(1).strip()
                confidence_scores.append(1.0)
            else:
                confidence_scores.append(0.0)

        # Extract optional fields
        for field_name in optional_fields:
            pattern = self._patterns[field_name]
            match = pattern.search(text)
            if match:
                extracted[field_name] = match.group(1).strip()
                confidence_scores.append(1.0)
            else:
                confidence_scores.append(0.0)

        # Parse and validate extracted values
        try:
            # Parse invoice number
            invoice_number = extracted.get("invoice_number", "UNKNOWN")

            # Parse dates
            invoice_date = self._parse_date(extracted.get("date"))
            due_date = self._parse_date(extracted.get("due_date"))

            # Parse amounts
            total_amount = self._parse_amount(extracted.get("amount", "0"))
            subtotal = self._parse_amount(extracted.get("subtotal", str(total_amount)))
            tax_amount = self._parse_amount(extracted.get("tax", "0"))

            # If no subtotal but we have total and tax, calculate it
            if subtotal == 0 and total_amount > 0:
                subtotal = total_amount - tax_amount

            # Parse currency
            currency = self._parse_currency(extracted.get("currency", "USD"))

            # Get vendor name
            vendor_name = extracted.get("vendor_name", "Unknown Vendor")

            # PO number
            po_number = extracted.get("po_number")

            # Payment terms
            payment_terms = extracted.get("payment_terms")

            # Validate we have minimum required fields
            if not invoice_number or total_amount == 0:
                return None, 0.0

            invoice_data = InvoiceData(
                vendor_name=vendor_name,
                invoice_number=invoice_number,
                invoice_date=invoice_date or date.today(),
                due_date=due_date,
                payment_terms=payment_terms,
                po_number=po_number,
                subtotal=subtotal,
                tax_amount=tax_amount,
                total_amount=total_amount,
                currency=currency,
                line_items=[],
                extraction_confidence=sum(confidence_scores) / len(confidence_scores),
                raw_text=text[:1000]  # Store first 1000 chars
            )

            # Calculate overall confidence
            required_fields = ["invoice_number", "date", "amount", "vendor_name"]
            found_required = sum(1 for f in required_fields if extracted.get(f))
            confidence = found_required / len(required_fields)

            return invoice_data, confidence

        except Exception as e:
            print(f"Field parsing error: {e}")
            return None, 0.0

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string into date object."""
        if not date_str:
            return None

        formats = [
            "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d",
            "%m-%d-%Y", "%d-%m-%Y",
            "%B %d, %Y", "%b %d, %Y",
            "%d %B %Y", "%d %b %Y"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None

    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string into float."""
        if not amount_str:
            return 0.0
        # Remove currency symbols and commas
        cleaned = re.sub(r"[,$€£RM]", "", amount_str)
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def _parse_currency(self, currency_str: str) -> Currency:
        """Parse currency string into Currency enum."""
        currency_map = {
            "$": Currency.USD,
            "usd": Currency.USD,
            "€": Currency.EUR,
            "eur": Currency.EUR,
            "£": Currency.GBP,
            "gbp": Currency.GBP,
            "rm": Currency.MYR,
            "myr": Currency.MYR,
            "sgd": Currency.SGD,
        }
        return currency_map.get(currency_str.lower(), Currency.USD)


class LLMDocumentProcessor(DocumentProcessor):
    """
    Enhanced document processor using LLM for extraction.

    This demonstrates Agentic AI capabilities by using LLM
    to intelligently extract and validate invoice data.
    """

    def __init__(self, llm_client=None):
        super().__init__()
        self.llm_client = llm_client

    async def process_with_llm(self, file_path: str) -> ExtractionResult:
        """
        Process document using LLM for enhanced extraction.

        This method demonstrates how to integrate with:
        - Azure OpenAI
        - OpenAI API
        - Other LLM providers
        """
        # First, get raw text using standard extraction
        base_result = await self.process_document(file_path)

        if not base_result.raw_text:
            return base_result

        # If LLM client is available, enhance extraction
        if self.llm_client:
            try:
                enhanced_data = await self._llm_extract(base_result.raw_text)
                if enhanced_data:
                    return ExtractionResult(
                        success=True,
                        raw_text=base_result.raw_text,
                        invoice_data=enhanced_data,
                        confidence=0.95,  # LLM extraction typically high confidence
                        extraction_method="llm_enhanced",
                        errors=[]
                    )
            except Exception as e:
                base_result.errors.append(f"LLM enhancement failed: {e}")

        return base_result

    async def _llm_extract(self, text: str) -> Optional[InvoiceData]:
        """Use LLM to extract structured invoice data."""

        extraction_prompt = f"""Extract invoice information from the following text and return as JSON.

Required fields:
- vendor_name: Company/vendor name
- invoice_number: Invoice number/ID
- invoice_date: Date in YYYY-MM-DD format
- total_amount: Total amount as number
- currency: Currency code (USD, EUR, GBP, MYR, SGD)

Optional fields:
- vendor_address: Full address
- due_date: Payment due date in YYYY-MM-DD format
- po_number: Purchase order reference
- subtotal: Amount before tax
- tax_amount: Tax amount
- payment_terms: Payment terms (e.g., NET30)

Text:
{text[:3000]}

Return only valid JSON, no explanation."""

        settings = get_settings()
        response = await self.llm_client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": extraction_prompt}],
            temperature=settings.LLM_TEMPERATURE,
        )
        result = json.loads(response.choices[0].message.content)

        return InvoiceData(
            vendor_name=result.get("vendor_name", "Unknown Vendor"),
            invoice_number=result.get("invoice_number", "UNKNOWN"),
            invoice_date=self._parse_date(result.get("invoice_date")) or date.today(),
            due_date=self._parse_date(result.get("due_date")),
            payment_terms=result.get("payment_terms"),
            po_number=result.get("po_number"),
            subtotal=float(result.get("subtotal", 0)),
            tax_amount=float(result.get("tax_amount", 0)),
            total_amount=float(result.get("total_amount", 0)),
            currency=self._parse_currency(result.get("currency", "USD")),
            line_items=[],
            extraction_confidence=0.95,
            raw_text=text[:1000],
        )


# Utility function for creating processor instance
def create_processor(use_llm: bool = False, llm_client=None) -> DocumentProcessor:
    """Factory function to create appropriate processor.

    When use_llm is True and no llm_client is provided, an OpenAI client
    pointing at the local Ollama instance is created automatically.
    """
    if use_llm:
        if llm_client is None:
            from openai import AsyncOpenAI
            settings = get_settings()
            llm_client = AsyncOpenAI(
                base_url=settings.OLLAMA_BASE_URL,
                api_key="ollama",  # Ollama doesn't require a real key
            )
        return LLMDocumentProcessor(llm_client)
    return DocumentProcessor()

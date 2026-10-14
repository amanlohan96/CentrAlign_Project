from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from tools.base import BaseTool
from pypdf import PdfReader


class FileSearchTool(BaseTool):
    """
    Searches file directories for relevant invoices, contracts, or business documents.
    Supports recursive globbing and keyword matching.
    """

    def __init__(self, base_workspace: Optional[Path] = None):
        self.base_workspace = base_workspace or Path(__file__).parent.parent
        schema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keywords or pattern to search for (e.g. 'Company X', 'Acme', 'invoice', '*.pdf')"
                },
                "directory": {
                    "type": "string",
                    "description": "Relative directory to search within (default: 'simulated_enterprise/document_vault')"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to search recursively into subfolders (default: true)"
                }
            },
            "required": ["query"]
        }
        super().__init__(
            name="file_search",
            description="Find files and invoices matching a search query or vendor name in the document vault.",
            parameters_schema=schema
        )

    def run(self, query: str, directory: str = "simulated_enterprise/document_vault", recursive: bool = True) -> Dict[str, Any]:
        target_dir = self.base_workspace / directory
        if not target_dir.exists():
            return {
                "found_files": [],
                "count": 0,
                "message": f"Directory '{directory}' does not exist."
            }

        q_lower = query.strip().lower()
        matched_files = []

        glob_method = target_dir.rglob if recursive else target_dir.glob
        for p in glob_method("*"):
            if p.is_file():
                filename_lower = p.name.lower()
                matches = False
                
                # Check Company X mapping specifically to Acme Cloud Corp
                if "company x" in q_lower:
                    if "acme" in filename_lower:
                        matches = True
                elif "acme" in q_lower:
                    if "acme" in filename_lower:
                        matches = True
                elif "apex" in q_lower:
                    if "apex" in filename_lower:
                        matches = True
                elif "nexus" in q_lower:
                    if "nexus" in filename_lower:
                        matches = True
                elif "cybertech" in q_lower or "gpu" in q_lower:
                    if "high_value" in filename_lower or "cybertech" in filename_lower:
                        matches = True
                else:
                    # Generic word boundary match
                    words = [w for w in re.split(r"[\s\-_]+", q_lower) if len(w) > 2]
                    if any(w in filename_lower for w in words):
                        matches = True

                if matches:
                    rel_path = str(p.relative_to(self.base_workspace)).replace("\\", "/")
                    # Extract date or recency signal: prefer november over october
                    recency_score = 0
                    if "nov" in filename_lower or "2024-11" in filename_lower or "9102" in filename_lower:
                        recency_score = 100
                    elif "oct" in filename_lower or "2024-10" in filename_lower:
                        recency_score = 50

                    matched_files.append({
                        "filename": p.name,
                        "relative_path": rel_path,
                        "size_bytes": p.stat().st_size,
                        "extension": p.suffix.lower(),
                        "modified_time": p.stat().st_mtime,
                        "recency_score": recency_score
                    })

        # Sort by recency score descending, then modified time descending
        matched_files.sort(key=lambda x: (x["recency_score"], x["modified_time"]), reverse=True)

        return {
            "query": query,
            "directory": directory,
            "count": len(matched_files),
            "found_files": matched_files,
            "message": f"Found {len(matched_files)} matching file(s) for query '{query}'."
        }


class DocumentReaderTool(BaseTool):
    """
    Reads the content of documents (PDF, TXT, JSON, MD).
    """

    def __init__(self, base_workspace: Optional[Path] = None):
        self.base_workspace = base_workspace or Path(__file__).parent.parent
        schema = {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative or absolute path to the file to read."
                }
            },
            "required": ["file_path"]
        }
        super().__init__(
            name="document_reader",
            description="Reads and extracts full text content from PDF, JSON, or text documents.",
            parameters_schema=schema
        )

    def run(self, file_path: str) -> Dict[str, Any]:
        p = Path(file_path)
        if not p.is_absolute():
            p = self.base_workspace / file_path

        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = p.suffix.lower()
        extracted_text = ""
        metadata = {
            "filename": p.name,
            "path": str(p),
            "size": p.stat().st_size,
            "format": suffix
        }

        if suffix == ".pdf":
            reader = PdfReader(str(p))
            pages_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                pages_text.append(text)
            extracted_text = "\n".join(pages_text).strip()
            metadata["page_count"] = len(reader.pages)
        elif suffix == ".json":
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                extracted_text = json.dumps(data, indent=2)
                metadata["json_data"] = data
        else:
            with open(p, "r", encoding="utf-8") as f:
                extracted_text = f.read()

        return {
            "success": True,
            "file_path": file_path,
            "content": extracted_text,
            "metadata": metadata
        }


class InvoiceEntityExtractorTool(BaseTool):
    """
    Extracts key structured invoice entities (vendor, invoice number, amount, due date)
    from unstructured document text or structured JSON.
    """

    def __init__(self):
        schema = {
            "type": "object",
            "properties": {
                "document_text": {
                    "type": "string",
                    "description": "The raw text or JSON string of the invoice."
                }
            },
            "required": ["document_text"]
        }
        super().__init__(
            name="invoice_entity_extractor",
            description="Parses invoice text and accurately extracts vendor name, invoice number, total amount, and due date.",
            parameters_schema=schema
        )

    def run(self, document_text: str) -> Dict[str, Any]:
        entities: Dict[str, Any] = {
            "vendor": None,
            "invoice_number": None,
            "amount": None,
            "due_date": None,
            "currency": "USD",
            "description": None,
            "confidence": 0.0
        }

        # Check if text is JSON
        try:
            parsed_json = json.loads(document_text)
            if isinstance(parsed_json, dict):
                entities["vendor"] = parsed_json.get("vendor")
                entities["invoice_number"] = parsed_json.get("invoice_number")
                entities["amount"] = float(parsed_json.get("total_amount", parsed_json.get("amount", 0)))
                entities["due_date"] = parsed_json.get("due_date")
                entities["currency"] = parsed_json.get("currency", "USD")
                entities["description"] = parsed_json.get("description", "Direct JSON ingestion")
                entities["confidence"] = 1.0
                return {"entities": entities, "extraction_method": "structured_json"}
        except (json.JSONDecodeError, ValueError):
            pass

        text = document_text

        # 1. Vendor
        vendor_match = re.search(r"Vendor:\s*([^\n\r]+)", text, re.IGNORECASE)
        if vendor_match:
            entities["vendor"] = vendor_match.group(1).strip()

        # 2. Invoice Number
        inv_match = re.search(r"Invoice\s*(?:Number|#|No\.?):\s*([A-Za-z0-9\-_]+)", text, re.IGNORECASE)
        if inv_match:
            entities["invoice_number"] = inv_match.group(1).strip()

        # 3. Total Amount
        amt_match = re.search(r"(?:Total\s*(?:Amount)?|Amount\s*Due):\s*\$?([0-9,]+(?:\.[0-9]{2})?)", text, re.IGNORECASE)
        if not amt_match:
            amt_match = re.search(r"\$([0-9,]+\.[0-9]{2})", text)

        if amt_match:
            clean_num = amt_match.group(1).replace(",", "")
            entities["amount"] = float(clean_num)

        # 4. Due Date
        date_match = re.search(r"Due\s*Date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", text, re.IGNORECASE)
        if not date_match:
            date_match = re.search(r"Due\s*Date:\s*([A-Za-z0-9\-/\s,]+)", text, re.IGNORECASE)

        if date_match:
            raw_date = date_match.group(1).strip()
            entities["due_date"] = raw_date

        # 5. Description
        desc_match = re.search(r"Description:\s*([^\n\r]+)", text, re.IGNORECASE)
        if desc_match:
            entities["description"] = desc_match.group(1).strip()
        else:
            line_item_match = re.search(r"1\.\s*([^\n\r$]+)", text)
            if line_item_match:
                entities["description"] = line_item_match.group(1).strip()
            else:
                entities["description"] = f"Invoice from {entities.get('vendor', 'vendor')}"

        required_keys = ["vendor", "invoice_number", "amount", "due_date"]
        found_keys = [k for k in required_keys if entities[k] is not None]
        confidence = len(found_keys) / len(required_keys)
        entities["confidence"] = round(confidence, 2)

        return {
            "entities": entities,
            "extraction_method": "regex_nlp_heuristics",
            "extracted_fields_count": len(found_keys)
        }

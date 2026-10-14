from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ERPInvoiceCreate(BaseModel):
    vendor: str
    invoice_number: str
    amount: float
    due_date: str  # Format: YYYY-MM-DD
    currency: str = "USD"
    description: Optional[str] = "Ingested invoice"
    source: str = "AI_WORKER"


class ERPInvoice(BaseModel):
    id: str
    vendor: str
    invoice_number: str
    amount: float
    due_date: str
    currency: str
    description: str
    status: str = "ENTERED"
    created_at: str
    source: str
    checksum: str


class EnterpriseERP:
    """
    Simulated Internal Company ERP & Accounting System.
    Provides in-memory persistent storage, business rules,
    validation logic, tamper-proof verification checksums, and audit logs.
    """

    def __init__(self):
        self.invoices: Dict[str, ERPInvoice] = {}
        self.audit_log: List[Dict[str, Any]] = []
        self._seed_initial_data()

    def _seed_initial_data(self):
        # Seed an older invoice for Acme Cloud Corp to verify "Find the latest invoice" capability
        oct_inv = ERPInvoice(
            id="ERP-INV-1001",
            vendor="Acme Cloud Corp",
            invoice_number="INV-2024-8140",
            amount=3200.00,
            due_date="2024-11-02",
            currency="USD",
            description="October Cloud Infrastructure Services",
            status="PAID",
            created_at="2024-10-03T10:00:00Z",
            source="MANUAL_ENTRY",
            checksum=self._compute_checksum("Acme Cloud Corp", "INV-2024-8140", 3200.00, "2024-11-02")
        )
        self.invoices[oct_inv.id] = oct_inv
        self._record_audit("SYSTEM_INIT", f"Seeded historical invoice {oct_inv.id}")

    def _compute_checksum(self, vendor: str, inv_num: str, amount: float, due_date: str) -> str:
        payload = f"{vendor.strip().lower()}|{inv_num.strip()}|{amount:.2f}|{due_date}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _record_audit(self, action: str, details: str, payload: Optional[Dict[str, Any]] = None):
        self.audit_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "details": details,
            "payload": payload or {}
        })


    def list_invoices(self, vendor: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        for inv in self.invoices.values():
            if vendor:
                if vendor.lower() not in inv.vendor.lower():
                    continue
            results.append(inv.model_dump())
        return results

    def get_invoice_by_id(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        inv = self.invoices.get(invoice_id)
        return inv.model_dump() if inv else None

    def get_invoice_by_number(self, invoice_number: str) -> Optional[Dict[str, Any]]:
        for inv in self.invoices.values():
            if inv.invoice_number.strip().lower() == invoice_number.strip().lower():
                return inv.model_dump()
        return None

    def create_invoice(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates an invoice with enterprise validation rules.
        Returns a dict with success: bool, and created record or error details.
        """
        vendor = data.get("vendor", "").strip()
        invoice_number = data.get("invoice_number", "").strip()
        amount_raw = data.get("amount")
        due_date = data.get("due_date", "").strip()
        currency = data.get("currency", "USD").strip()
        description = data.get("description", "Ingested invoice").strip()
        source = data.get("source", "AI_WORKER")

        # 1. Required fields validation
        if not vendor:
            return {"success": False, "error_code": "MISSING_VENDOR", "message": "Field 'vendor' is required."}
        if not invoice_number:
            return {"success": False, "error_code": "MISSING_INVOICE_NUMBER", "message": "Field 'invoice_number' is required."}
        if amount_raw is None:
            return {"success": False, "error_code": "MISSING_AMOUNT", "message": "Field 'amount' is required."}

        # 2. Amount numeric & positive check
        try:
            amount = float(amount_raw)
            if amount <= 0:
                return {"success": False, "error_code": "INVALID_AMOUNT", "message": "Invoice amount must be greater than zero."}
        except (ValueError, TypeError):
            return {"success": False, "error_code": "INVALID_AMOUNT_FORMAT", "message": f"Invalid amount '{amount_raw}'. Must be a valid float."}

        # 3. Date format validation (Expects YYYY-MM-DD)
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        if not re.match(date_pattern, due_date):
            return {
                "success": False,
                "error_code": "INVALID_DATE_FORMAT",
                "message": f"Due date '{due_date}' violates ISO-8601 requirement (YYYY-MM-DD). Please re-format (e.g. 2024-12-04)."
            }

        # 4. Duplicate invoice check
        for existing in self.invoices.values():
            if existing.invoice_number.lower() == invoice_number.lower() and existing.vendor.lower() == vendor.lower():
                return {
                    "success": False,
                    "error_code": "DUPLICATE_INVOICE",
                    "message": f"Invoice '{invoice_number}' for vendor '{vendor}' already exists in ERP with ID {existing.id}."
                }

        # 5. Generate new ERP Record ID
        next_seq = 1000 + len(self.invoices) + 1
        record_id = f"ERP-INV-{next_seq}"
        checksum = self._compute_checksum(vendor, invoice_number, amount, due_date)

        new_invoice = ERPInvoice(
            id=record_id,
            vendor=vendor,
            invoice_number=invoice_number,
            amount=amount,
            due_date=due_date,
            currency=currency,
            description=description,
            status="ENTERED",
            created_at=datetime.now(timezone.utc).isoformat(),
            source=source,
            checksum=checksum
        )


        self.invoices[record_id] = new_invoice
        self._record_audit(
            action="CREATE_INVOICE",
            details=f"Created invoice record {record_id} for vendor {vendor} (Amount: {currency} {amount:.2f})",
            payload={"id": record_id, "invoice_number": invoice_number, "amount": amount, "checksum": checksum}
        )

        return {
            "success": True,
            "record": new_invoice.model_dump(),
            "message": f"Successfully created invoice {record_id} in Internal ERP.",
            "verification_checksum": checksum
        }

    def verify_invoice_record(self, invoice_number: str, expected_amount: float, expected_due_date: str) -> Dict[str, Any]:
        """
        Independent verification function that validates database state matches ground truth.
        """
        match = None
        for inv in self.invoices.values():
            if inv.invoice_number.strip().lower() == invoice_number.strip().lower():
                match = inv
                break

        if not match:
            return {
                "verified": False,
                "reason": f"Invoice number '{invoice_number}' not found in ERP records.",
                "record": None
            }

        amount_match = abs(match.amount - float(expected_amount)) < 0.01
        date_match = match.due_date.strip() == expected_due_date.strip()
        expected_checksum = self._compute_checksum(match.vendor, match.invoice_number, match.amount, match.due_date)
        integrity_valid = (match.checksum == expected_checksum)

        all_matched = amount_match and date_match and integrity_valid

        return {
            "verified": all_matched,
            "record_id": match.id,
            "vendor": match.vendor,
            "amount_match": amount_match,
            "date_match": date_match,
            "integrity_valid": integrity_valid,
            "stored_amount": match.amount,
            "expected_amount": expected_amount,
            "stored_due_date": match.due_date,
            "expected_due_date": expected_due_date,
            "status": match.status,
            "checksum": match.checksum
        }

    def get_web_portal_dom(self) -> Dict[str, Any]:
        """
        Simulated DOM tree of the ERP Web Portal page for browser tool automation.
        """
        invoice_rows = [
            {
                "tag": "tr",
                "attributes": {"data-id": inv.id},
                "cells": [inv.id, inv.vendor, inv.invoice_number, f"${inv.amount:,.2f}", inv.due_date, inv.status]
            }
            for inv in self.invoices.values()
        ]

        return {
            "url": "http://internal-erp.local/portal/invoices",
            "title": "Corporate Finance Portal - Accounts Payable",
            "interactive_elements": [
                {"id": "input-vendor", "name": "vendor", "tag": "input", "type": "text", "placeholder": "Enter Vendor Name"},
                {"id": "input-inv-num", "name": "invoice_number", "tag": "input", "type": "text", "placeholder": "Invoice #"},
                {"id": "input-amount", "name": "amount", "tag": "input", "type": "number", "placeholder": "Total Amount ($)"},
                {"id": "input-due-date", "name": "due_date", "tag": "input", "type": "date", "placeholder": "YYYY-MM-DD"},
                {"id": "input-description", "name": "description", "tag": "input", "type": "text", "placeholder": "Memo / Description"},
                {"id": "btn-submit-invoice", "tag": "button", "type": "submit", "text": "Post Invoice to Ledger"},
                {"id": "btn-search", "tag": "button", "text": "Search Invoices"}
            ],
            "existing_records_count": len(self.invoices),
            "table_data": invoice_rows
        }


# Global singleton instance for simulated enterprise
erp_instance = EnterpriseERP()

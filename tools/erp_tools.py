from __future__ import annotations
from typing import Any, Dict, Optional
from tools.base import BaseTool
from simulated_enterprise.erp_portal import erp_instance


class ERPPostInvoiceTool(BaseTool):
    """
    Submits an invoice into the internal Enterprise Accounting / ERP system.
    Handles business validations and provides rich status responses.
    """

    def __init__(self):
        schema = {
            "type": "object",
            "properties": {
                "vendor": {"type": "string", "description": "Legal name of the vendor or supplier."},
                "invoice_number": {"type": "string", "description": "Unique vendor invoice identifier."},
                "amount": {"type": "number", "description": "Total invoice amount to be recorded."},
                "due_date": {"type": "string", "description": "Payment due date in ISO format (YYYY-MM-DD)."},
                "currency": {"type": "string", "description": "Currency code (e.g. 'USD'). Default is USD."},
                "description": {"type": "string", "description": "Memo or line item summary."}
            },
            "required": ["vendor", "invoice_number", "amount", "due_date"]
        }
        super().__init__(
            name="erp_post_invoice",
            description="Posts an approved invoice into the internal enterprise accounting/ERP system.",
            parameters_schema=schema
        )

    def run(self, vendor: str, invoice_number: str, amount: float, due_date: str,
            currency: str = "USD", description: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "vendor": vendor,
            "invoice_number": invoice_number,
            "amount": amount,
            "due_date": due_date,
            "currency": currency,
            "description": description or f"Invoice from {vendor}",
            "source": "AI_WORKER"
        }
        
        result = erp_instance.create_invoice(payload)
        return result


class ERPListInvoicesTool(BaseTool):
    """
    Retrieves recorded invoices from the internal ERP system to inspect current state.
    """

    def __init__(self):
        schema = {
            "type": "object",
            "properties": {
                "vendor": {"type": "string", "description": "Optional vendor filter string."}
            }
        }
        super().__init__(
            name="erp_list_invoices",
            description="Queries the internal ERP system to view currently registered invoices.",
            parameters_schema=schema
        )

    def run(self, vendor: Optional[str] = None) -> Dict[str, Any]:
        records = erp_instance.list_invoices(vendor=vendor)
        return {
            "total_count": len(records),
            "vendor_filter": vendor,
            "invoices": records
        }


class ERPVerifyInvoiceTool(BaseTool):
    """
    Performs independent verification that an invoice exists in the ERP
    with 100% data fidelity against ground truth values.
    """

    def __init__(self):
        schema = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string", "description": "The invoice number to verify."},
                "expected_amount": {"type": "number", "description": "The expected amount."},
                "expected_due_date": {"type": "string", "description": "The expected due date (YYYY-MM-DD)."}
            },
            "required": ["invoice_number", "expected_amount", "expected_due_date"]
        }
        super().__init__(
            name="erp_verify_invoice",
            description="Independently verifies that an invoice record was accurately recorded in the internal ERP.",
            parameters_schema=schema
        )

    def run(self, invoice_number: str, expected_amount: float, expected_due_date: str) -> Dict[str, Any]:
        verification = erp_instance.verify_invoice_record(
            invoice_number=invoice_number,
            expected_amount=expected_amount,
            expected_due_date=expected_due_date
        )
        return verification

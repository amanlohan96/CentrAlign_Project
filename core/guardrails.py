from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from core.models import ApprovalRequest, PlanStep, WorkingMemory


class SafetyGuardrails:
    """
    Enterprise Safety and Human-in-the-Loop (HITL) Guardrail Engine.
    Ensures autonomous worker does not execute high-risk or ambiguous actions
    without human oversight or clarification.
    """

    def __init__(self, high_value_threshold: float = 5000.00):
        self.high_value_threshold = high_value_threshold

    def evaluate_step(
        self,
        step: PlanStep,
        memory: WorkingMemory,
        existing_approvals: Optional[List[ApprovalRequest]] = None
    ) -> Tuple[bool, Optional[ApprovalRequest]]:
        """
        Evaluates whether a planned step violates safety policies and requires human approval/clarification.
        Returns: (requires_approval: bool, approval_request: Optional[ApprovalRequest])
        """
        # If human already approved this action/step, proceed without re-triggering
        if existing_approvals:
            for app in existing_approvals:
                if app.status == "APPROVED":
                    return False, None

        tool_name = step.tool_name or ""
        args = step.arguments or {}

        # Policy 1: High-Value Financial Ingestion Guardrail
        # If posting an invoice or updating an ERP with an amount exceeding threshold
        if tool_name in ["erp_post_invoice", "browser_fill_form"]:
            amount = args.get("amount") or memory.get_entity("amount")
            if amount is not None:
                try:
                    amount_val = float(amount)
                    if amount_val >= self.high_value_threshold:
                        req = ApprovalRequest(
                            reason=f"High-value financial action detected: Amount (${amount_val:,.2f}) exceeds autonomous ingestion limit of ${self.high_value_threshold:,.2f}.",
                            policy_triggered="POLICY-FIN-001 (High-Value Ingestion Threshold)",
                            proposed_action=f"Submit invoice '{args.get('invoice_number', memory.get_entity('invoice_number', 'unknown'))}' for ${amount_val:,.2f} to Internal ERP.",
                            context={
                                "amount": amount_val,
                                "vendor": args.get("vendor", memory.get_entity("vendor")),
                                "invoice_number": args.get("invoice_number", memory.get_entity("invoice_number")),
                                "due_date": args.get("due_date", memory.get_entity("due_date"))
                            }
                        )
                        return True, req
                except (ValueError, TypeError):
                    pass

        # Policy 2: Ambiguous Multiple Candidates Guardrail
        if memory.get_entity("ambiguous_vendor_candidates"):
            candidates = memory.get_entity("ambiguous_vendor_candidates")
            if len(candidates) > 1:
                req = ApprovalRequest(
                    reason=f"Multiple ambiguous vendor document matches found ({len(candidates)} files). Human clarification required.",
                    policy_triggered="POLICY-DOC-002 (Ambiguous Source Clarification)",
                    proposed_action="Choose specific target invoice document to process.",
                    context={"candidates": candidates}
                )
                return True, req

        return False, None

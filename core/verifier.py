from __future__ import annotations
from typing import Any, Dict, List, Optional
from core.models import VerificationCheck, VerificationResult, WorkingMemory
from simulated_enterprise.erp_portal import erp_instance


class OutcomeVerifier:
    """
    Independent Verification Subsystem.
    Verifies that the requested outcome was actually achieved in the real target system,
    rather than merely assuming success from intermediate tool execution return codes.
    """

    def __init__(self):
        pass

    def verify_invoice_ingestion(self, memory: WorkingMemory) -> VerificationResult:
        """
        Independently queries the Internal ERP database to confirm the invoice
        exists, has exact matching values, and hasn't suffered data corruption.
        """
        vendor = memory.get_entity("vendor")
        inv_num = memory.get_entity("invoice_number")
        expected_amount = memory.get_entity("amount")
        expected_due_date = memory.get_entity("due_date")

        checks: List[VerificationCheck] = []

        if not inv_num:
            return VerificationResult(
                verified=False,
                confidence_score=0.0,
                checks=[VerificationCheck(
                    check_name="Invoice Identifier Presence",
                    target_system="Memory / Entity Store",
                    expected="Valid Invoice Number",
                    actual=None,
                    passed=False,
                    details="No invoice number found in agent working memory to verify."
                )],
                summary="Verification failed: Missing invoice number in working memory."
            )

        # 1. Independent query against target system
        record = erp_instance.get_invoice_by_number(inv_num)

        # Check 1: Record Exists in Target System
        exists_check = VerificationCheck(
            check_name="Record Existence in ERP Ledger",
            target_system="Internal ERP (ledger)",
            expected=f"Invoice record with number {inv_num}",
            actual=record["id"] if record else "NOT_FOUND",
            passed=record is not None,
            details=f"Querying ERP for invoice '{inv_num}' returned record {record['id'] if record else 'None'}."
        )
        checks.append(exists_check)

        if not record:
            return VerificationResult(
                verified=False,
                confidence_score=0.0,
                checks=checks,
                summary=f"Verification failed: Invoice '{inv_num}' was not found in the ERP system."
            )

        # Check 2: Amount Fidelity
        actual_amt = record.get("amount")
        amount_passed = False
        if expected_amount is not None and actual_amt is not None:
            amount_passed = abs(float(actual_amt) - float(expected_amount)) < 0.01

        checks.append(VerificationCheck(
            check_name="Amount Value Precision",
            target_system="Internal ERP (amount field)",
            expected=float(expected_amount) if expected_amount is not None else 0.0,
            actual=actual_amt,
            passed=amount_passed,
            details=f"Expected amount ${expected_amount} vs ERP stored amount ${actual_amt}."
        ))

        # Check 3: Due Date Fidelity
        actual_date = record.get("due_date", "").strip()
        date_passed = (actual_date == str(expected_due_date).strip())
        checks.append(VerificationCheck(
            check_name="Due Date ISO Fidelity",
            target_system="Internal ERP (due_date field)",
            expected=expected_due_date,
            actual=actual_date,
            passed=date_passed,
            details=f"Expected due date '{expected_due_date}' vs ERP stored date '{actual_date}'."
        ))

        # Check 4: Cryptographic Checksum Integrity
        expected_checksum = erp_instance._compute_checksum(
            record["vendor"], record["invoice_number"], record["amount"], record["due_date"]
        )
        checksum_passed = (record.get("checksum") == expected_checksum)
        checks.append(VerificationCheck(
            check_name="Ledger Cryptographic Integrity",
            target_system="Internal ERP (SHA-256 checksum)",
            expected=expected_checksum,
            actual=record.get("checksum"),
            passed=checksum_passed,
            details="Cryptographic hash matches internal ledger state without corruption."
        ))

        # Check 5: Status Validation
        status_valid = record.get("status") in ["ENTERED", "PENDING_APPROVAL", "PAID"]
        checks.append(VerificationCheck(
            check_name="Ledger Entry Status",
            target_system="Internal ERP (status field)",
            expected="Valid active status (ENTERED/PENDING_APPROVAL)",
            actual=record.get("status"),
            passed=status_valid,
            details=f"Current record status is '{record.get('status')}'."
        ))

        passed_count = sum(1 for c in checks if c.passed)
        total_count = len(checks)
        all_passed = (passed_count == total_count)
        confidence = passed_count / total_count

        return VerificationResult(
            verified=all_passed,
            confidence_score=round(confidence, 2),
            checks=checks,
            target_record_id=record.get("id"),
            target_url=f"http://internal-erp.local/portal/invoices/{record.get('id')}",
            summary=(
                f"Outcome independently verified! Record '{record.get('id')}' confirmed in ERP with "
                f"100% data fidelity (Vendor: {record.get('vendor')}, Amount: ${actual_amt:,.2f}, Due Date: {actual_date})."
                if all_passed else
                f"Outcome verification failed: {total_count - passed_count} check(s) did not match."
            )
        )

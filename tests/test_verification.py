import pytest
from core.verifier import OutcomeVerifier
from core.models import WorkingMemory
from simulated_enterprise.erp_portal import erp_instance


def test_outcome_verifier_detects_data_tampering_or_discrepancy():
    """
    Tests that OutcomeVerifier catches mismatches between source ground truth
    and database records (e.g. incorrect amount or corrupted state).
    """
    # 1. Post a test invoice
    erp_instance.create_invoice({
        "vendor": "Acme Cloud Corp",
        "invoice_number": "INV-TEST-99",
        "amount": 500.00,
        "due_date": "2024-12-01",
        "description": "Test entry"
    })

    verifier = OutcomeVerifier()

    # Case A: Memory expects $500.00 -> Should pass
    mem_correct = WorkingMemory()
    mem_correct.record_entity("vendor", "Acme Cloud Corp")
    mem_correct.record_entity("invoice_number", "INV-TEST-99")
    mem_correct.record_entity("amount", 500.00)
    mem_correct.record_entity("due_date", "2024-12-01")

    res_correct = verifier.verify_invoice_ingestion(mem_correct)
    assert res_correct.verified is True
    assert res_correct.confidence_score == 1.0

    # Case B: Memory expects $800.00 (discrepancy!) -> Should fail verification
    mem_mismatch = WorkingMemory()
    mem_mismatch.record_entity("vendor", "Acme Cloud Corp")
    mem_mismatch.record_entity("invoice_number", "INV-TEST-99")
    mem_mismatch.record_entity("amount", 800.00)
    mem_mismatch.record_entity("due_date", "2024-12-01")

    res_mismatch = verifier.verify_invoice_ingestion(mem_mismatch)
    assert res_mismatch.verified is False
    assert any(c.check_name == "Amount Value Precision" and not c.passed for c in res_mismatch.checks)


def test_outcome_verifier_missing_record():
    """
    Tests that verification fails when the record was never created in the target system.
    """
    verifier = OutcomeVerifier()
    mem_ghost = WorkingMemory()
    mem_ghost.record_entity("invoice_number", "INV-GHOST-404")
    mem_ghost.record_entity("amount", 100.00)
    mem_ghost.record_entity("due_date", "2024-12-01")

    res_ghost = verifier.verify_invoice_ingestion(mem_ghost)
    assert res_ghost.verified is False
    assert "not found in the ERP system" in res_ghost.summary

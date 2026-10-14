import pytest
from core.agent import AutonomousAIWorker
from core.models import TaskStatus, PlanStep, StepStatus
from simulated_enterprise.erp_portal import erp_instance


def test_self_healing_date_format_recovery():
    """
    Tests that when an invoice has a non-ISO date format (e.g. '12/04/2024'),
    the ERP validation error is detected, self-healing normalizer is triggered,
    and the task successfully recovers and completes.
    """
    worker = AutonomousAIWorker()
    task = worker.create_task("Enter invoice with messy date into ERP")
    
    # Pre-populate memory with non-ISO date
    task.memory.record_entity("vendor", "Acme Cloud Corp")
    task.memory.record_entity("invoice_number", "INV-HEAL-001")
    task.memory.record_entity("amount", 1250.00)
    task.memory.record_entity("due_date", "12/04/2024")  # non-ISO format
    task.memory.record_entity("raw_date", "12/04/2024")

    # Manually configure steps to test post + self-healing
    task.steps = [
        PlanStep(
            id="step_erp_post",
            title="Post invoice with unnormalized date",
            tool_name="erp_post_invoice",
            arguments={"vendor": "Acme Cloud Corp", "invoice_number": "INV-HEAL-001", "amount": 1250.00, "due_date": "12/04/2024"},
            status=StepStatus.PENDING,
            max_retries=3
        ),
        PlanStep(
            id="step_verify",
            title="Verify invoice",
            tool_name="erp_verify_invoice",
            arguments={"invoice_number": "INV-HEAL-001", "expected_amount": 1250.00, "expected_due_date": "2024-12-04"},
            status=StepStatus.PENDING,
            depends_on=["step_erp_post"]
        )
    ]

    completed_task = worker.execute_task(task)

    # Verify self healing inserted recovery step and completed
    assert completed_task.status == TaskStatus.COMPLETED
    assert completed_task.memory.get_entity("due_date") == "2024-12-04"
    assert completed_task.evidence.verification.verified is True


def test_self_healing_directory_search_fallback():
    """
    Tests that if a file is misplaced in subdirectories, the worker triggers fallback
    search to locate it.
    """
    from tools.file_tools import FileSearchTool
    search_tool = FileSearchTool()
    
    # Misplaced file is in simulated_enterprise/document_vault/invoices/unprocessed_scans
    res = search_tool.run(query="Nexus", directory="simulated_enterprise/document_vault", recursive=True)
    assert res["count"] >= 1
    assert "nexus_invoice_unprocessed.txt" in res["found_files"][0]["filename"]

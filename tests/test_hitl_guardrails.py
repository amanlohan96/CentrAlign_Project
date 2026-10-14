import pytest
from core.agent import AutonomousAIWorker
from core.models import TaskStatus, PlanStep, StepStatus


def test_hitl_guardrail_triggers_on_high_value_invoice():
    """
    Tests that when an invoice exceeds the $5,000 threshold,
    the worker pauses in WAITING_FOR_APPROVAL and requires human decision.
    """
    worker = AutonomousAIWorker(guardrail_threshold=5000.00)
    task = worker.create_task("Ingest high value GPU workstation invoice")

    # Set up memory with $18,500 invoice
    task.memory.record_entity("vendor", "Global CyberTech Hardware Inc")
    task.memory.record_entity("invoice_number", "GCT-2024-9901")
    task.memory.record_entity("amount", 18500.00)
    task.memory.record_entity("due_date", "2024-11-28")

    task.steps = [
        PlanStep(
            id="step_erp_post",
            title="Enter high value invoice into ERP",
            tool_name="erp_post_invoice",
            arguments={"vendor": "Global CyberTech Hardware Inc", "invoice_number": "GCT-2024-9901", "amount": 18500.00, "due_date": "2024-11-28"},
            status=StepStatus.PENDING
        )
    ]

    # Execute task
    paused_task = worker.execute_task(task)

    # Must be paused for human approval
    assert paused_task.status == TaskStatus.WAITING_FOR_APPROVAL
    assert len(paused_task.approval_requests) == 1
    approval_req = paused_task.approval_requests[0]
    assert "High-value financial action detected" in approval_req.reason
    assert approval_req.status == "PENDING"

    # Test Scenario A: User Approves
    resumed_task = worker.handle_approval_response(
        task=paused_task,
        request_id=approval_req.id,
        approved=True,
        user_response="Approved by Finance VP for AI lab."
    )
    assert resumed_task.status == TaskStatus.COMPLETED
    assert resumed_task.evidence.verification.verified is True


def test_hitl_guardrail_user_rejection():
    """
    Tests that if the user rejects the high-value action, the task halts safely.
    """
    worker = AutonomousAIWorker(guardrail_threshold=5000.00)
    task = worker.create_task("Ingest high value invoice")
    task.memory.record_entity("vendor", "Unknown Supplier")
    task.memory.record_entity("invoice_number", "REJ-001")
    task.memory.record_entity("amount", 99000.00)
    task.memory.record_entity("due_date", "2024-12-01")

    task.steps = [
        PlanStep(
            id="step_erp_post",
            title="Post large invoice",
            tool_name="erp_post_invoice",
            arguments={"vendor": "Unknown Supplier", "invoice_number": "REJ-001", "amount": 99000.00, "due_date": "2024-12-01"},
            status=StepStatus.PENDING
        )
    ]

    paused_task = worker.execute_task(task)
    req_id = paused_task.approval_requests[0].id

    # User Rejects
    cancelled_task = worker.handle_approval_response(
        task=paused_task,
        request_id=req_id,
        approved=False,
        user_response="Rejected: Unauthorized purchase order."
    )
    assert cancelled_task.status == TaskStatus.CANCELLED
    assert "User declined approval" in cancelled_task.error or "Rejected" in cancelled_task.error

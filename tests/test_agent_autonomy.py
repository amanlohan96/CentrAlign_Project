import pytest
from core.agent import AutonomousAIWorker
from core.models import TaskStatus, StepStatus
from simulated_enterprise.erp_portal import erp_instance


def test_end_to_end_invoice_task_autonomy():
    """
    Evaluates archetypal task:
    'Find the latest invoice from Company X, extract the amount and due date, enter it into our internal system, and tell me once it is done.'
    """
    worker = AutonomousAIWorker()
    goal = "Find the latest invoice from Company X, extract the amount and due date, enter it into our internal system, and tell me once it is done."
    
    # 1. Autonomous Task Creation & Initial Planning
    task = worker.create_task(goal)
    assert task.status == TaskStatus.PLANNING
    assert len(task.steps) >= 5

    # 2. Autonomous Execution
    completed_task = worker.execute_task(task)

    # 3. Assertions on Execution & State
    assert completed_task.status == TaskStatus.COMPLETED
    assert completed_task.error is None

    # Verify working memory captures extracted entities
    mem = completed_task.memory
    assert mem.get_entity("invoice_number") == "INV-2024-9102"
    assert mem.get_entity("amount") == 4850.00
    assert mem.get_entity("due_date") == "2024-12-04"
    assert "Acme" in mem.get_entity("vendor", "")

    # Verify independent verification subsystem passed
    assert completed_task.evidence is not None
    assert completed_task.evidence.verification is not None
    assert completed_task.evidence.verification.verified is True
    assert completed_task.evidence.verification.confidence_score == 1.0

    # Verify target record exists in ERP ledger
    rec_id = completed_task.evidence.verification.target_record_id
    erp_record = erp_instance.get_invoice_by_id(rec_id)
    assert erp_record is not None
    assert erp_record["amount"] == 4850.00
    assert erp_record["due_date"] == "2024-12-04"
    assert erp_record["source"] == "AI_WORKER"

    # Verify audit events were recorded
    assert len(completed_task.evidence.audit_trail_events) > 5

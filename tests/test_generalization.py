import pytest
from core.agent import AutonomousAIWorker
from core.models import TaskStatus, PlanStep, StepStatus
from simulated_enterprise.erp_portal import erp_instance


def test_generalization_json_structured_invoice():
    """
    Tests processing an invoice delivered as a structured JSON file (Apex Logistics).
    """
    worker = AutonomousAIWorker()
    goal = "Find the latest invoice from Apex, extract the amount and due date, enter it into our internal system, and tell me once it is done."
    task = worker.create_task(goal)
    completed_task = worker.execute_task(task)

    assert completed_task.status == TaskStatus.COMPLETED
    assert completed_task.memory.get_entity("invoice_number") == "APX-7741"
    assert completed_task.memory.get_entity("amount") == 1420.50
    assert completed_task.memory.get_entity("due_date") == "2024-12-10"
    assert completed_task.evidence.verification.verified is True


def test_generalization_simulated_browser_entry():
    """
    Tests performing invoice entry via Simulated Web Browser Form rather than API.
    """
    from tools.browser_tools import (
        BrowserNavigateTool, BrowserFillFormTool, BrowserClickButtonTool
    )
    nav_tool = BrowserNavigateTool()
    fill_tool = BrowserFillFormTool()
    click_tool = BrowserClickButtonTool()

    nav_tool.run(url="http://internal-erp.local/portal/invoices")
    fill_tool.run(field_name="vendor", value="Browser Automated Supplier")
    fill_tool.run(field_name="invoice_number", value="INV-WEB-889")
    fill_tool.run(field_name="amount", value=750.00)
    fill_tool.run(field_name="due_date", value="2024-12-15")
    
    click_res = click_tool.run(button_id="btn-submit-invoice")
    assert click_res["status_code"] == 200
    assert click_res["submission_result"]["success"] is True

    # Verify created in ERP
    inv = erp_instance.get_invoice_by_number("INV-WEB-889")
    assert inv is not None
    assert inv["source"] == "SIMULATED_BROWSER_WEB_PORTAL"

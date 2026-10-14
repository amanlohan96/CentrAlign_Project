from fastapi.testclient import TestClient
from ui.server import app

client = TestClient(app)


def test_api_health_and_invoices():
    response = client.get("/api/erp/invoices")
    assert response.status_code == 200
    invoices = response.json()
    assert isinstance(invoices, list)
    assert len(invoices) >= 1


def test_api_task_lifecycle_and_verification():
    payload = {
        "goal": "Find the latest invoice from Company X, extract the amount and due date, enter it into our internal system, and tell me once it is done.",
        "auto_execute": True,
        "guardrail_threshold": 5000.0
    }
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 200
    task_data = response.json()
    assert task_data["status"] == "COMPLETED"
    assert task_data["evidence"]["verification"]["verified"] is True
    assert task_data["evidence"]["verification"]["confidence_score"] == 1.0


def test_api_hitl_approval_lifecycle():
    # Submit high-value task exceeding $5000 threshold
    payload = {
        "goal": "Ingest high value GPU workstation invoice from Global CyberTech into ERP and alert finance.",
        "auto_execute": True,
        "guardrail_threshold": 5000.0
    }
    response = client.post("/api/tasks", json=payload)
    assert response.status_code == 200
    task_data = response.json()
    assert task_data["status"] == "WAITING_FOR_APPROVAL"
    assert len(task_data["approval_requests"]) == 1

    req_id = task_data["approval_requests"][0]["id"]
    task_id = task_data["task_id"]

    # Approve task
    approval_payload = {
        "request_id": req_id,
        "approved": True,
        "user_response": "Approved by Finance Director"
    }
    app_response = client.post(f"/api/tasks/{task_id}/approve", json=approval_payload)
    assert app_response.status_code == 200
    resumed_data = app_response.json()
    assert resumed_data["status"] == "COMPLETED"
    assert resumed_data["evidence"]["verification"]["verified"] is True

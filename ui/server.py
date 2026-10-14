from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from core.agent import AutonomousAIWorker
from core.models import TaskRun, TaskStatus
from simulated_enterprise.erp_portal import erp_instance
from simulated_enterprise.document_vault.generate_documents import setup_sample_vault

app = FastAPI(title="Autonomous AI Task Worker Mission Control", version="1.0.0")

# Store active tasks in memory
tasks_db: Dict[str, TaskRun] = {}
worker = AutonomousAIWorker()

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)


class CreateTaskRequest(BaseModel):
    goal: str
    auto_execute: bool = True
    guardrail_threshold: float = 5000.00


class ApprovalDecisionRequest(BaseModel):
    request_id: str
    approved: bool
    user_response: Optional[str] = None


@app.post("/api/tasks")
def create_task_endpoint(req: CreateTaskRequest):
    custom_worker = AutonomousAIWorker(guardrail_threshold=req.guardrail_threshold)
    task = custom_worker.create_task(req.goal)
    tasks_db[task.task_id] = task

    if req.auto_execute:
        custom_worker.execute_task(task)

    return task.model_dump()


@app.get("/api/tasks/{task_id}")
def get_task_endpoint(task_id: str):
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.model_dump()


@app.post("/api/tasks/{task_id}/execute")
def execute_task_endpoint(task_id: str):
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    worker.execute_task(task)
    return task.model_dump()


@app.post("/api/tasks/{task_id}/approve")
def approve_task_endpoint(task_id: str, req: ApprovalDecisionRequest):
    task = tasks_db.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    worker.handle_approval_response(
        task=task,
        request_id=req.request_id,
        approved=req.approved,
        user_response=req.user_response
    )
    return task.model_dump()


@app.get("/api/erp/invoices")
def get_erp_invoices():
    return erp_instance.list_invoices()


@app.get("/api/erp/audit-log")
def get_erp_audit_log():
    return erp_instance.audit_log[-20:]


@app.post("/api/reset")
def reset_environment():
    global erp_instance, tasks_db
    from simulated_enterprise.erp_portal import EnterpriseERP
    import simulated_enterprise.erp_portal as ep
    ep.erp_instance = EnterpriseERP()
    setup_sample_vault(Path(__file__).parent.parent / "simulated_enterprise" / "document_vault")
    tasks_db.clear()
    return {"message": "Environment successfully reset to clean state."}


# Mount static assets
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
def serve_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>Autonomous AI Worker Dashboard API is running.</h1>")

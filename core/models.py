from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    WAITING_FOR_CLARIFICATION = "WAITING_FOR_CLARIFICATION"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    RETRIED = "RETRIED"


class ToolCall(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=utc_now_iso)


class ToolResult(BaseModel):
    call_id: str
    tool_name: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    artifacts: Dict[str, Any] = Field(default_factory=dict)


class PlanStep(BaseModel):
    id: str
    title: str
    description: str = ""
    tool_name: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    status: StepStatus = StepStatus.PENDING
    depends_on: List[str] = Field(default_factory=list)
    retries: int = 0
    max_retries: int = 3
    result: Optional[ToolResult] = None
    reasoning: Optional[str] = None
    alternative_strategy: Optional[str] = None


class WorkingMemory(BaseModel):
    discovered_entities: Dict[str, Any] = Field(default_factory=dict)
    scratchpad: List[str] = Field(default_factory=list)
    visited_locations: List[str] = Field(default_factory=list)
    context_variables: Dict[str, Any] = Field(default_factory=dict)
    error_history: List[Dict[str, Any]] = Field(default_factory=list)

    def note(self, observation: str) -> None:
        ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
        self.scratchpad.append(f"[{ts}] {observation}")

    def record_entity(self, key: str, value: Any) -> None:
        self.discovered_entities[key] = value

    def get_entity(self, key: str, default: Any = None) -> Any:
        return self.discovered_entities.get(key, default)

    def record_error(self, step_id: str, error_msg: str, recovery_attempted: Optional[str] = None) -> None:
        self.error_history.append({
            "step_id": step_id,
            "error": error_msg,
            "recovery_attempted": recovery_attempted
        })



class VerificationCheck(BaseModel):
    check_name: str
    target_system: str
    expected: Any
    actual: Any
    passed: bool
    details: str


class VerificationResult(BaseModel):
    verified: bool
    confidence_score: float = 1.0
    checks: List[VerificationCheck] = Field(default_factory=list)
    summary: str
    verified_at: str = Field(default_factory=utc_now_iso)
    target_record_id: Optional[str] = None
    target_url: Optional[str] = None


class ApprovalRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    reason: str
    policy_triggered: str
    proposed_action: str
    context: Dict[str, Any] = Field(default_factory=dict)
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED
    user_response: Optional[str] = None
    requested_at: str = Field(default_factory=utc_now_iso)
    resolved_at: Optional[str] = None


class ExecutionEvidence(BaseModel):
    summary: str
    entities_processed: Dict[str, Any] = Field(default_factory=dict)
    artifacts_created: List[Dict[str, Any]] = Field(default_factory=list)
    system_records_affected: List[Dict[str, Any]] = Field(default_factory=list)
    verification: Optional[VerificationResult] = None
    audit_trail_events: List[Dict[str, Any]] = Field(default_factory=list)
    duration_seconds: float = 0.0


class TaskRun(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    goal: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    steps: List[PlanStep] = Field(default_factory=list)
    current_step_index: int = 0
    memory: WorkingMemory = Field(default_factory=WorkingMemory)
    approval_requests: List[ApprovalRequest] = Field(default_factory=list)
    evidence: Optional[ExecutionEvidence] = None
    error: Optional[str] = None

    def add_audit_event(self, action: str, details: Dict[str, Any]) -> None:
        if self.evidence is None:
            self.evidence = ExecutionEvidence(summary="In Progress")
        self.evidence.audit_trail_events.append({
            "timestamp": utc_now_iso(),
            "action": action,
            "details": details
        })

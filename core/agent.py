from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from core.models import (
    ApprovalRequest, ExecutionEvidence, PlanStep, StepStatus,
    TaskRun, TaskStatus, ToolResult, WorkingMemory, utc_now_iso
)
from core.memory import AgentMemoryManager
from core.planner import TaskPlanner
from core.guardrails import SafetyGuardrails
from core.verifier import OutcomeVerifier
from core.llm_engine import BaseCognitiveEngine, get_default_engine

if TYPE_CHECKING:
    from tools.registry import ToolRegistry


class AutonomousAIWorker:
    """
    Autonomous AI Task Worker.
    Executes natural language tasks through hierarchical planning,
    ReAct tool execution, working memory, error detection, self-healing,
    human-in-the-loop guardrails, and independent outcome verification.
    """

    def __init__(
        self,
        registry: Optional[Any] = None,
        cognitive_engine: Optional[BaseCognitiveEngine] = None,
        guardrail_threshold: float = 5000.00
    ):
        if registry is None:
            from tools.registry import tool_registry
            self.registry = tool_registry
        else:
            self.registry = registry
        self.cognitive_engine = cognitive_engine or get_default_engine()
        self.planner = TaskPlanner()
        self.guardrails = SafetyGuardrails(high_value_threshold=guardrail_threshold)
        self.verifier = OutcomeVerifier()

    def create_task(self, goal: str) -> TaskRun:
        task = TaskRun(goal=goal)
        task.status = TaskStatus.PLANNING
        task.steps = self.planner.create_initial_plan(goal)
        task.add_audit_event("TASK_CREATED", {"goal": goal, "initial_steps_count": len(task.steps)})
        return task

    def execute_task(
        self,
        task: TaskRun,
        step_callback: Optional[Callable[[TaskRun, PlanStep], None]] = None
    ) -> TaskRun:
        """
        Executes task steps until completion, failure, or human approval requirement.
        """
        start_time = time.perf_counter()
        task.status = TaskStatus.EXECUTING
        task.updated_at = utc_now_iso()

        while task.current_step_index < len(task.steps):
            if task.status in [TaskStatus.WAITING_FOR_APPROVAL, TaskStatus.WAITING_FOR_CLARIFICATION]:
                break

            step = task.steps[task.current_step_index]

            # 1. Dynamic argument binding from working memory
            self._bind_step_arguments(step, task.memory)

            # 2. Human-in-the-Loop Safety Guardrails Check
            requires_approval, approval_req = self.guardrails.evaluate_step(
                step, task.memory, existing_approvals=task.approval_requests
            )
            if requires_approval and approval_req:
                task.status = TaskStatus.WAITING_FOR_APPROVAL
                task.approval_requests.append(approval_req)
                task.add_audit_event("PAUSED_FOR_APPROVAL", {
                    "step_id": step.id,
                    "reason": approval_req.reason,
                    "policy": approval_req.policy_triggered
                })
                if step_callback:
                    step_callback(task, step)
                break

            # 3. Execute Step
            step.status = StepStatus.IN_PROGRESS
            task.add_audit_event("STEP_START", {"step_id": step.id, "title": step.title})

            if step_callback:
                step_callback(task, step)

            # Tool Execution
            result = self._execute_step(step, task)

            # 4. Observe & Update Memory
            if result.success:
                step.status = StepStatus.SUCCESS
                step.result = result
                self._update_memory_from_result(step, result, task.memory)
                task.add_audit_event("STEP_SUCCESS", {"step_id": step.id, "output_preview": str(result.output)[:120]})
                task.current_step_index += 1
            else:
                step.retries += 1
                task.memory.record_error(step.id, result.error or "Unknown error")
                task.add_audit_event("STEP_FAILURE", {"step_id": step.id, "error": result.error, "retry": step.retries})

                # 5. Self-Healing & Error Recovery
                recovered = self._attempt_self_healing(step, result, task)
                if not recovered:
                    if step.retries >= step.max_retries:
                        step.status = StepStatus.FAILED
                        task.status = TaskStatus.FAILED
                        task.error = f"Step '{step.title}' failed after {step.retries} attempts: {result.error}"
                        break
                    else:
                        step.status = StepStatus.RETRIED

            if step_callback:
                step_callback(task, step)

        # 6. Verification Phase
        if task.status == TaskStatus.EXECUTING and task.current_step_index >= len(task.steps):
            task.status = TaskStatus.VERIFYING
            task.add_audit_event("VERIFICATION_START", {"goal": task.goal})

            verification = self.verifier.verify_invoice_ingestion(task.memory)
            
            total_duration = time.perf_counter() - start_time
            summary_text = self.cognitive_engine.summarize_completion(
                task.goal,
                task.memory.model_dump(),
                verification.summary
            )

            task.evidence = ExecutionEvidence(
                summary=summary_text,
                entities_processed=task.memory.discovered_entities,
                artifacts_created=[{"type": "erp_record", "id": verification.target_record_id}],
                system_records_affected=[{"system": "Internal ERP", "record_id": verification.target_record_id}],
                verification=verification,
                audit_trail_events=task.evidence.audit_trail_events if task.evidence else [],
                duration_seconds=round(total_duration, 2)
            )

            if verification.verified:
                task.status = TaskStatus.COMPLETED
                task.add_audit_event("TASK_COMPLETED", {"verified": True, "record_id": verification.target_record_id})
            else:
                task.status = TaskStatus.FAILED
                task.error = f"Execution completed but independent verification failed: {verification.summary}"
                task.add_audit_event("TASK_FAILED_VERIFICATION", {"reason": verification.summary})

        task.updated_at = utc_now_iso()
        return task

    def handle_approval_response(self, task: TaskRun, request_id: str, approved: bool, user_response: Optional[str] = None) -> TaskRun:
        """
        Handles human resolution of a pending approval/clarification request.
        """
        for req in task.approval_requests:
            if req.id == request_id and req.status == "PENDING":
                req.status = "APPROVED" if approved else "REJECTED"
                req.user_response = user_response
                req.resolved_at = utc_now_iso()
                task.add_audit_event("APPROVAL_RESOLVED", {"request_id": request_id, "approved": approved, "notes": user_response})

                if approved:
                    task.status = TaskStatus.EXECUTING
                    return self.execute_task(task)
                else:
                    task.status = TaskStatus.CANCELLED
                    task.error = f"Task halted by user rejection: {user_response or 'User declined approval.'}"
                    return task

        return task

    def _bind_step_arguments(self, step: PlanStep, memory: WorkingMemory) -> None:
        """
        Resolves arguments dynamically from working memory.
        """
        if not step.arguments:
            step.arguments = {}

        tool = step.tool_name
        if tool == "document_reader":
            if not step.arguments.get("file_path"):
                target_file = memory.get_entity("selected_invoice_file")
                if target_file:
                    step.arguments["file_path"] = target_file

        elif tool == "invoice_entity_extractor":
            if not step.arguments.get("document_text"):
                doc_text = memory.get_entity("raw_document_text")
                if doc_text:
                    step.arguments["document_text"] = doc_text

        elif tool == "erp_post_invoice":
            if not step.arguments.get("vendor"):
                step.arguments["vendor"] = memory.get_entity("vendor", "")
            if not step.arguments.get("invoice_number"):
                step.arguments["invoice_number"] = memory.get_entity("invoice_number", "")
            if not step.arguments.get("amount"):
                step.arguments["amount"] = memory.get_entity("amount", 0.0)
            # If date was healed in memory, use healed date
            normalized_date = memory.get_entity("due_date")
            if normalized_date:
                step.arguments["due_date"] = normalized_date
            elif not step.arguments.get("due_date"):
                step.arguments["due_date"] = ""

        elif tool == "erp_verify_invoice":
            if not step.arguments.get("invoice_number"):
                step.arguments["invoice_number"] = memory.get_entity("invoice_number", "")
            if not step.arguments.get("expected_amount"):
                step.arguments["expected_amount"] = memory.get_entity("amount", 0.0)
            normalized_date = memory.get_entity("due_date")
            if normalized_date:
                step.arguments["expected_due_date"] = normalized_date
            elif not step.arguments.get("expected_due_date"):
                step.arguments["expected_due_date"] = ""

        elif tool == "notification_dispatcher":
            if not step.arguments.get("message"):
                vendor = memory.get_entity("vendor", "Vendor")
                inv_num = memory.get_entity("invoice_number", "")
                amt = memory.get_entity("amount", 0.0)
                step.arguments["message"] = (
                    f"Completed ingestion of invoice {inv_num} from {vendor} for ${amt:,.2f} into Internal ERP."
                )

    def _execute_step(self, step: PlanStep, task: TaskRun) -> ToolResult:
        if not step.tool_name:
            return ToolResult(
                call_id=f"step_{step.id}",
                tool_name="none",
                success=True,
                output="Conceptual step completed."
            )

        res = self.registry.execute(
            tool_name=step.tool_name,
            arguments=step.arguments or {},
            call_id=f"call_{step.id}_{step.retries}"
        )
        # Catch domain-level failures reported in payload dicts
        if res.success and isinstance(res.output, dict) and res.output.get("success") is False:
            res.success = False
            res.error = res.output.get("message") or res.output.get("error") or "Operation failed"

        return res


    def _update_memory_from_result(self, step: PlanStep, result: ToolResult, memory: WorkingMemory) -> None:
        """
        Extracts facts and updates working memory based on tool outputs.
        """
        output = result.output

        if step.tool_name == "file_search" and isinstance(output, dict):
            found_files = output.get("found_files", [])
            memory.note(f"Found {len(found_files)} files matching query '{output.get('query')}'.")
            if found_files:
                selected = found_files[0]["relative_path"]
                memory.record_entity("selected_invoice_file", selected)
                memory.record_entity("all_matching_files", [f["relative_path"] for f in found_files])
                memory.note(f"Selected latest invoice candidate: {selected}")

        elif step.tool_name == "document_reader" and isinstance(output, dict):
            content = output.get("content", "")
            memory.record_entity("raw_document_text", content)
            memory.visited_locations.append(output.get("file_path", ""))
            memory.note(f"Read document content ({len(content)} characters).")

        elif step.tool_name == "invoice_entity_extractor" and isinstance(output, dict):
            entities = output.get("entities", {})
            for k, v in entities.items():
                if v is not None:
                    memory.record_entity(k, v)
            memory.note(f"Extracted entities: Vendor={entities.get('vendor')}, Inv#={entities.get('invoice_number')}, Amount={entities.get('amount')}, DueDate={entities.get('due_date')}")

        elif step.tool_name == "erp_post_invoice" and isinstance(output, dict):
            if output.get("success"):
                rec = output.get("record", {})
                memory.record_entity("erp_record_id", rec.get("id"))
                memory.record_entity("erp_checksum", rec.get("checksum"))
                memory.note(f"Created ERP record {rec.get('id')}.")
            else:
                result.success = False
                result.error = output.get("message", "ERP rejected invoice submission.")

        elif step.tool_name == "date_normalizer" and isinstance(output, dict):
            if output.get("success"):
                normalized = output.get("normalized_date")
                memory.record_entity("due_date", normalized)
                memory.note(f"Normalized due date to ISO: {normalized}")

        elif step.tool_name == "browser_navigate" and isinstance(output, dict):
            memory.note(f"Navigated browser to {output.get('current_url')}")

        elif step.tool_name == "browser_click_button" and isinstance(output, dict):
            sub_res = output.get("submission_result", {})
            if sub_res.get("success"):
                rec = sub_res.get("record", {})
                memory.record_entity("erp_record_id", rec.get("id"))
                memory.note(f"Created ERP record via Web Portal: {rec.get('id')}.")

    def _attempt_self_healing(self, step: PlanStep, result: ToolResult, task: TaskRun) -> bool:
        """
        Attempts self-healing by generating and inserting recovery steps.
        """
        recovery_step = self.planner.generate_recovery_step(
            failed_step=step,
            error_msg=result.error or "",
            context=task.memory.discovered_entities
        )

        if recovery_step:
            task.add_audit_event("SELF_HEALING_TRIGGERED", {
                "failed_step": step.id,
                "recovery_action": recovery_step.title
            })
            task.steps.insert(task.current_step_index, recovery_step)
            return True

        return False

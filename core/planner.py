from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from core.models import PlanStep, StepStatus


class TaskPlanner:
    """
    Hierarchical Task Planner.
    Analyzes natural language goals, determines required capabilities,
    and produces structured sequence of executable steps.
    """

    def __init__(self):
        pass

    def create_initial_plan(self, goal: str) -> List[PlanStep]:
        """
        Decomposes high-level goal into an initial step plan.
        Recognizes goals related to invoices, data entry, reports, or verification.
        """
        goal_lower = goal.lower()
        steps: List[PlanStep] = []

        # Detect vendor / company target
        vendor_match = re.search(r"(?:from|for|company)\s+([A-Za-z0-9\s]+?)(?:,|\.|\band\b|extract|$)", goal, re.IGNORECASE)
        vendor_query = vendor_match.group(1).strip() if vendor_match else "Company X"

        if "invoice" in goal_lower:
            # 1. Search Files
            steps.append(PlanStep(
                id="step_1_search_invoices",
                title=f"Find invoice files for {vendor_query}",
                description=f"Search document storage vault for latest invoice documents from {vendor_query}.",
                tool_name="file_search",
                arguments={"query": vendor_query, "directory": "simulated_enterprise/document_vault", "recursive": True},
                status=StepStatus.PENDING,
                max_retries=2
            ))

            # 2. Read Document
            steps.append(PlanStep(
                id="step_2_read_document",
                title="Read document content",
                description="Extract full text from the discovered latest invoice file (PDF/JSON/TXT).",
                tool_name="document_reader",
                arguments={},  # Will be dynamically populated from Step 1 observation
                status=StepStatus.PENDING,
                depends_on=["step_1_search_invoices"],
                max_retries=2
            ))

            # 3. Extract Entities
            steps.append(PlanStep(
                id="step_3_extract_entities",
                title="Extract invoice amount, due date, and metadata",
                description="Parse invoice text to extract vendor, invoice number, amount, and due date.",
                tool_name="invoice_entity_extractor",
                arguments={},  # Will be populated from Step 2
                status=StepStatus.PENDING,
                depends_on=["step_2_read_document"]
            ))

            # 4. Ingest into Internal ERP
            steps.append(PlanStep(
                id="step_4_erp_ingestion",
                title="Enter invoice into internal ERP system",
                description="Post the validated invoice details into the internal accounting/ERP system.",
                tool_name="erp_post_invoice",
                arguments={},  # Will be populated from extracted entities
                status=StepStatus.PENDING,
                depends_on=["step_3_extract_entities"],
                max_retries=3,
                alternative_strategy="browser_web_portal_entry"
            ))

            # 5. Independent Verification
            steps.append(PlanStep(
                id="step_5_verify_outcome",
                title="Independently verify ERP record creation",
                description="Verify that the invoice was recorded in the ERP ledger with 100% data fidelity.",
                tool_name="erp_verify_invoice",
                arguments={},  # Will be populated from Step 3 & 4
                status=StepStatus.PENDING,
                depends_on=["step_4_erp_ingestion"]
            ))

            # 6. Notify completion if requested
            if any(term in goal_lower for term in ["tell me", "notify", "alert", "let me know", "done"]):
                steps.append(PlanStep(
                    id="step_6_notify_completion",
                    title="Send completion notification with evidence",
                    description="Dispatch final summary and verification proof to user.",
                    tool_name="notification_dispatcher",
                    arguments={},
                    status=StepStatus.PENDING,
                    depends_on=["step_5_verify_outcome"]
                ))
        else:
            # Generic fallback plan for exploratory or general tasks
            steps.append(PlanStep(
                id="step_1_inspect_workspace",
                title="Inspect available files and environment",
                description="Search directory for relevant resources to solve user goal.",
                tool_name="file_search",
                arguments={"query": goal, "directory": "simulated_enterprise/document_vault"},
                status=StepStatus.PENDING
            ))
            steps.append(PlanStep(
                id="step_2_execute_core_goal",
                title="Execute primary objective",
                description=f"Autonomously accomplish: {goal}",
                tool_name="notification_dispatcher",
                arguments={"message": f"Processed request: {goal}"},
                status=StepStatus.PENDING,
                depends_on=["step_1_inspect_workspace"]
            ))

        return steps

    def generate_recovery_step(self, failed_step: PlanStep, error_msg: str, context: Dict[str, Any]) -> Optional[PlanStep]:
        """
        Self-Healing Engine:
        Analyzes the failure reason and constructs an intelligent recovery or alternative step.
        """
        # Case 1: Date format error from ERP validation
        if "INVALID_DATE_FORMAT" in error_msg or "violates ISO-8601" in error_msg:
            raw_date = context.get("raw_date") or context.get("due_date", "")
            return PlanStep(
                id=f"{failed_step.id}_heal_date",
                title="Self-heal: Normalize invalid date format",
                description="Normalize non-standard due date string into strict ISO-8601 (YYYY-MM-DD).",
                tool_name="date_normalizer",
                arguments={"raw_date": raw_date},
                status=StepStatus.PENDING
            )

        # Case 2: File not found in primary directory -> search archive or unprocessed scans
        if "File not found" in error_msg or failed_step.tool_name == "file_search" and "0 matching file" in error_msg:
            return PlanStep(
                id=f"{failed_step.id}_search_fallback",
                title="Self-heal: Deep search in archive & unprocessed scans",
                description="Search subdirectories and archive folders with broader wildcard query.",
                tool_name="file_search",
                arguments={"query": "*", "directory": "simulated_enterprise/document_vault/invoices", "recursive": True},
                status=StepStatus.PENDING
            )

        # Case 3: API posting failed -> Fallback to simulated browser portal UI
        if failed_step.tool_name == "erp_post_invoice" and failed_step.alternative_strategy == "browser_web_portal_entry":
            return PlanStep(
                id=f"{failed_step.id}_browser_fallback",
                title="Alternative Strategy: Enter via Web Browser Portal",
                description="Direct API failed. Automating web browser navigation and form entry in company portal.",
                tool_name="browser_navigate",
                arguments={"url": "http://internal-erp.local/portal/invoices"},
                status=StepStatus.PENDING
            )

        return None

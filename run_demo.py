#!/usr/bin/env python3
"""
Autonomous AI Task Worker - Interactive Demo CLI Runner
"""

from __future__ import annotations
import sys
import io

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm

from core.agent import AutonomousAIWorker
from core.models import TaskStatus, StepStatus
from simulated_enterprise.erp_portal import erp_instance

console = Console(highlight=False)


def print_banner():
    banner = """
+----------------------------------------------------------------------+
|                     AUTONOMOUS AI TASK WORKER                        |
|        Goal Decomposition • ReAct Loop • Self-Healing • HITL         |
|                 Independent Outcome Verification                     |
+----------------------------------------------------------------------+
"""
    console.print(banner, style="bold cyan")


def run_scenario(goal: str, guardrail_threshold: float = 5000.00):
    console.print(Panel(f"[bold white]Target Goal:[/bold white] [yellow]{goal}[/yellow]", title="Task Ingestion", border_style="cyan"))

    worker = AutonomousAIWorker(guardrail_threshold=guardrail_threshold)
    task = worker.create_task(goal)

    console.print(f"[bold green][OK] Initial Plan Generated ({len(task.steps)} steps):[/bold green]")
    table = Table(title="Initial Execution Plan (DAG)", border_style="blue")
    table.add_column("Step #", style="cyan", width=8)
    table.add_column("Title", style="white")
    table.add_column("Assigned Tool", style="magenta")
    table.add_column("Status", style="yellow")

    for i, s in enumerate(task.steps, 1):
        table.add_row(str(i), s.title, s.tool_name or "internal_logic", s.status.value)
    console.print(table)
    console.print()

    console.print("[bold cyan]>> Initiating Autonomous Execution...[/bold cyan]\n")

    # Step callback to show real-time progress
    def step_cb(t, step):
        if step.status == StepStatus.IN_PROGRESS:
            console.print(f"[bold blue][RUN] [{step.id}][/bold blue] Executing: {step.title} (Tool: {step.tool_name})...")
        elif step.status == StepStatus.SUCCESS:
            out_preview = str(step.result.output)[:90] if step.result else ""
            console.print(f"[bold green][OK]  [{step.id}][/bold green] Success! Output: [dim]{out_preview}...[/dim]")
        elif step.status == StepStatus.FAILED:
            console.print(f"[bold red][ERR] [{step.id}][/bold red] Failed! Error: {step.result.error if step.result else 'Error'}")

    completed_task = worker.execute_task(task, step_callback=step_cb)

    # Check if halted by HITL Guardrail
    if completed_task.status == TaskStatus.WAITING_FOR_APPROVAL:
        req = completed_task.approval_requests[-1]
        console.print()
        console.print(Panel(
            f"[bold red]POLICY TRIGGERED:[/bold red] {req.policy_triggered}\n"
            f"[bold yellow]Reason:[/bold yellow] {req.reason}\n"
            f"[bold cyan]Proposed Action:[/bold cyan] {req.proposed_action}\n"
            f"[bold white]Context:[/bold white] {req.context}",
            title="[!] HUMAN-IN-THE-LOOP APPROVAL REQUIRED",
            border_style="red"
        ))

        approved = Confirm.ask("\n[bold yellow]Authorize the AI Worker to proceed with this high-value action?[/bold yellow]", default=True)
        note = Prompt.ask("Operator authorization note", default="Approved by Operations Manager")

        console.print(f"\n[bold green]Resuming task with user decision ({'APPROVED' if approved else 'REJECTED'})...[/bold green]\n")
        completed_task = worker.handle_approval_response(
            task=completed_task,
            request_id=req.id,
            approved=approved,
            user_response=note
        )

    console.print()
    # Final Output Display
    if completed_task.status == TaskStatus.COMPLETED:
        console.print(Panel("[bold green][OK] TASK COMPLETED AND INDEPENDENTLY VERIFIED![/bold green]", border_style="green"))

        # Working Memory
        mem_table = Table(title="Working Memory & Discovered Entities", border_style="magenta")
        mem_table.add_column("Entity Key", style="cyan")
        mem_table.add_column("Extracted Value", style="white")
        for k, v in completed_task.memory.discovered_entities.items():
            mem_table.add_row(k, str(v))
        console.print(mem_table)
        console.print()

        # Verification Certificate
        if completed_task.evidence and completed_task.evidence.verification:
            v = completed_task.evidence.verification
            verif_table = Table(title=f"Independent Verification Report (Target Record: {v.target_record_id})", border_style="green")
            verif_table.add_column("Check Name", style="white")
            verif_table.add_column("Target System", style="cyan")
            verif_table.add_column("Expected", style="yellow")
            verif_table.add_column("Actual", style="green")
            verif_table.add_column("Result", style="bold green")

            for chk in v.checks:
                verif_table.add_row(chk.check_name, chk.target_system, str(chk.expected), str(chk.actual), "PASS" if chk.passed else "FAIL")
            console.print(verif_table)
            console.print()

        # Evidence Summary
        if completed_task.evidence:
            console.print(Panel(completed_task.evidence.summary, title="Concise Completion Summary", border_style="cyan"))

    else:
        console.print(Panel(f"[bold red]Task Status: {completed_task.status.value}[/bold red]\nError: {completed_task.error}", border_style="red"))

    console.print("\n[dim]----------------------------------------------------------------------[/dim]\n")


def main():
    print_banner()

    scenarios = [
        ("Archetypal Scenario", "Find the latest invoice from Company X, extract the amount and due date, enter it into our internal system, and tell me once it is done.", 5000.00),
        ("Human-In-The-Loop Guardrail ($18.5k GPU Hardware)", "Ingest high value GPU workstation invoice from Global CyberTech into ERP and alert finance.", 5000.00),
        ("Self-Healing & Format Recovery", "Enter invoice with messy date into ERP", 5000.00),
        ("Structured JSON Document Processing", "Find the latest invoice from Apex, extract the amount and due date, enter it into our internal system, and tell me once it is done.", 5000.00),
        ("Custom Goal (Input your own)", "", 5000.00)
    ]

    console.print("[bold yellow]Available Demonstration Scenarios:[/bold yellow]")
    for i, (name, goal, _) in enumerate(scenarios, 1):
        console.print(f" [bold cyan]{i}[/bold cyan]. {name}")

    choice = Prompt.ask("\nSelect a scenario to run", choices=[str(i) for i in range(1, len(scenarios) + 1)], default="1")
    selected_idx = int(choice) - 1

    name, goal, threshold = scenarios[selected_idx]

    if selected_idx == 4:
        goal = Prompt.ask("\nEnter your natural language task")
        threshold = float(Prompt.ask("Set HITL approval threshold ($)", default="5000"))

    run_scenario(goal, guardrail_threshold=threshold)


if __name__ == "__main__":
    main()

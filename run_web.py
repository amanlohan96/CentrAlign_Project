#!/usr/bin/env python3
"""
Launcher for Autonomous AI Task Worker Web Mission Control
"""

import uvicorn
from rich.console import Console
from rich.panel import Panel

console = Console()

if __name__ == "__main__":
    banner = """
    [bold green]★ Autonomous AI Task Worker - Mission Control Dashboard ★[/bold green]
    
    Access the live interactive UI at:
    [bold cyan]http://127.0.0.1:8000[/bold cyan]
    
    Features available:
    • Natural Language Task Execution
    • Real-time ReAct Reasoning DAG & Step Cards
    • Live Working Memory & Blackboard State
    • Interactive Human-in-the-Loop (HITL) Approval Modal
    • Independent Outcome Verification Certificate
    • Live Simulated Enterprise ERP Ledger & Audit Trail
    """
    console.print(Panel(banner, border_style="cyan"))
    uvicorn.run("ui.server:app", host="127.0.0.1", port=8000, reload=False)

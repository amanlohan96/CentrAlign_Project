from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from tools.base import BaseTool


class NotificationDispatcherTool(BaseTool):
    """
    Sends execution completion notifications and evidence summaries
    via simulated channels (Slack, Email, Internal Webhook).
    """

    def __init__(self):
        schema = {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Target recipient or channel (e.g. '@user', '#finance-ops')."},
                "channel": {"type": "string", "description": "Channel type: 'slack', 'email', or 'system_alert'. Default: 'slack'."},
                "message": {"type": "string", "description": "Concise summary of completion and evidence."}
            },
            "required": ["message"]
        }
        super().__init__(
            name="notification_dispatcher",
            description="Sends a notification and summary of completion to the user or team channel.",
            parameters_schema=schema
        )
        self.dispatched_messages: List[Dict[str, Any]] = []

    def run(self, message: str, recipient: str = "@user", channel: str = "slack") -> Dict[str, Any]:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel": channel,
            "recipient": recipient,
            "message": message,
            "status": "DELIVERED"
        }

        self.dispatched_messages.append(event)
        return {
            "delivered": True,
            "channel": channel,
            "recipient": recipient,
            "message_preview": message[:120] + "..." if len(message) > 120 else message,
            "delivery_receipt": f"MSG-RECEIPT-{len(self.dispatched_messages):04d}"
        }


class DateNormalizerTool(BaseTool):
    """
    Normalizes various date formats into standard ISO 8601 (YYYY-MM-DD).
    Used for self-healing date validation errors.
    """

    def __init__(self):
        schema = {
            "type": "object",
            "properties": {
                "raw_date": {"type": "string", "description": "Date string in any format (e.g. '12/04/2024', 'November 4, 2024')."}
            },
            "required": ["raw_date"]
        }
        super().__init__(
            name="date_normalizer",
            description="Normalizes messy or ambiguous date strings into required ISO format (YYYY-MM-DD).",
            parameters_schema=schema
        )

    def run(self, raw_date: str) -> Dict[str, Any]:
        cleaned = raw_date.strip()
        # Direct ISO match
        if re.match(r"^\d{4}-\d{2}-\d{2}$", cleaned):
            return {"normalized_date": cleaned, "format": "ISO-8601", "success": True}

        formats_to_try = [
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
            "%d %b %Y",
            "%Y/%m/%d",
            "%Y.%m.%d"
        ]
        for fmt in formats_to_try:
            try:
                dt = datetime.strptime(cleaned, fmt)
                iso = dt.strftime("%Y-%m-%d")
                return {"normalized_date": iso, "original_format": fmt, "success": True}
            except ValueError:
                continue

        return {
            "normalized_date": cleaned,
            "success": False,
            "error": f"Could not determine date format for '{raw_date}'."
        }


class CalculatorTool(BaseTool):
    """
    Performs verified mathematical computations and checks.
    """

    def __init__(self):
        schema = {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Arithmetic expression to evaluate (e.g. '3500 + 850 + 500')."}
            },
            "required": ["expression"]
        }
        super().__init__(
            name="calculator",
            description="Evaluates arithmetic expressions to verify line item totals and calculations.",
            parameters_schema=schema
        )

    def run(self, expression: str) -> Dict[str, Any]:
        # Safe evaluation of basic numbers and operators
        cleaned = re.sub(r"[^0-9\+\-\*\/\.\(\)\s]", "", expression)
        try:
            # Safely evaluate restricted math expression
            result = float(eval(cleaned, {"__builtins__": {}}, {}))
            return {"expression": expression, "result": result, "success": True}
        except Exception as e:
            return {"expression": expression, "error": str(e), "success": False}

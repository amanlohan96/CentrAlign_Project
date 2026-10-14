from __future__ import annotations
from abc import ABC, abstractmethod
import time
from typing import Any, Dict, Optional
from core.models import ToolResult


class BaseTool(ABC):
    """
    Abstract base class for all tools available to the Autonomous AI Task Worker.
    Provides timing, standardized error handling, and parameter schemas.
    """

    def __init__(self, name: str, description: str, parameters_schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters_schema = parameters_schema

    @abstractmethod
    def run(self, **kwargs) -> Any:
        """Core execution logic implemented by child tools."""
        pass

    def execute(self, call_id: str, **kwargs) -> ToolResult:
        """
        Safe execution wrapper that records duration and handles exceptions cleanly.
        """
        start_time = time.perf_counter()
        try:
            output = self.run(**kwargs)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            artifacts = {}
            if isinstance(output, dict) and "artifacts" in output:
                artifacts = output.pop("artifacts")

            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=True,
                output=output,
                error=None,
                execution_time_ms=round(duration_ms, 2),
                artifacts=artifacts
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ToolResult(
                call_id=call_id,
                tool_name=self.name,
                success=False,
                output=None,
                error=f"Tool '{self.name}' failed with error: {str(e)}",
                execution_time_ms=round(duration_ms, 2)
            )

    def to_schema(self) -> Dict[str, Any]:
        """Returns JSON schema definition for LLM tool calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema
            }
        }

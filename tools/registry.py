from __future__ import annotations
from typing import Any, Dict, List, Optional
from tools.base import BaseTool
from tools.file_tools import FileSearchTool, DocumentReaderTool, InvoiceEntityExtractorTool
from tools.erp_tools import ERPPostInvoiceTool, ERPListInvoicesTool, ERPVerifyInvoiceTool
from tools.browser_tools import (
    BrowserNavigateTool, BrowserInspectDOMTool, BrowserFillFormTool, BrowserClickButtonTool
)
from tools.system_tools import NotificationDispatcherTool, DateNormalizerTool, CalculatorTool


class ToolRegistry:
    """
    Central registry for all tools accessible by the Autonomous AI Task Worker.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        default_tools = [
            FileSearchTool(),
            DocumentReaderTool(),
            InvoiceEntityExtractorTool(),
            ERPPostInvoiceTool(),
            ERPListInvoicesTool(),
            ERPVerifyInvoiceTool(),
            BrowserNavigateTool(),
            BrowserInspectDOMTool(),
            BrowserFillFormTool(),
            BrowserClickButtonTool(),
            NotificationDispatcherTool(),
            DateNormalizerTool(),
            CalculatorTool()
        ]
        for t in default_tools:
            self.register(t)

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict[str, Any]]:
        return [tool.to_schema() for tool in self._tools.values()]

    def execute(self, tool_name: str, arguments: Dict[str, Any], call_id: Optional[str] = None):
        tool = self.get(tool_name)
        if not tool:
            from core.models import ToolResult
            return ToolResult(
                call_id=call_id or "unknown",
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' not found in registry."
            )
        return tool.execute(call_id=call_id or f"call_{tool_name}", **arguments)


# Global default registry instance
tool_registry = ToolRegistry()

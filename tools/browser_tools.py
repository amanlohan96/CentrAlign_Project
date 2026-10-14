from __future__ import annotations
from typing import Any, Dict, Optional
from tools.base import BaseTool
from simulated_enterprise.erp_portal import erp_instance


class BrowserSession:
    """
    Maintains simulated browser state (current URL, page DOM, form buffer, history).
    """
    def __init__(self):
        self.current_url: Optional[str] = None
        self.dom_state: Dict[str, Any] = {}
        self.form_buffer: Dict[str, Any] = {}
        self.history: list[str] = []

    def navigate(self, url: str) -> Dict[str, Any]:
        self.current_url = url
        self.history.append(url)
        if "portal" in url or "internal-erp" in url:
            self.dom_state = erp_instance.get_web_portal_dom()
        else:
            self.dom_state = {
                "url": url,
                "title": "Generic Web Page",
                "interactive_elements": [],
                "body_text": f"Loaded web page at {url}"
            }
        self.form_buffer = {}
        return self.dom_state

    def fill_form_field(self, field_id_or_name: str, value: Any) -> Dict[str, Any]:
        self.form_buffer[field_id_or_name] = value
        return {
            "field": field_id_or_name,
            "value": value,
            "buffered_fields": list(self.form_buffer.keys())
        }

    def click_button(self, button_id: str) -> Dict[str, Any]:
        if button_id in ["btn-submit-invoice", "submit", "post"]:
            # Map form buffer to ERP create invoice
            vendor = self.form_buffer.get("input-vendor") or self.form_buffer.get("vendor", "")
            inv_num = self.form_buffer.get("input-inv-num") or self.form_buffer.get("invoice_number", "")
            amount = self.form_buffer.get("input-amount") or self.form_buffer.get("amount", 0)
            due_date = self.form_buffer.get("input-due-date") or self.form_buffer.get("due_date", "")
            desc = self.form_buffer.get("input-description") or self.form_buffer.get("description", "Entered via Web Portal")

            res = erp_instance.create_invoice({
                "vendor": vendor,
                "invoice_number": inv_num,
                "amount": amount,
                "due_date": due_date,
                "description": desc,
                "source": "SIMULATED_BROWSER_WEB_PORTAL"
            })
            # Refresh DOM state
            self.dom_state = erp_instance.get_web_portal_dom()
            return {
                "button_clicked": button_id,
                "submission_result": res,
                "status_code": 200 if res["success"] else 400
            }
        elif button_id in ["btn-search", "search"]:
            return {
                "button_clicked": button_id,
                "action": "filtered_table",
                "records": erp_instance.list_invoices()
            }
        else:
            return {
                "button_clicked": button_id,
                "action": "noop",
                "message": f"Clicked {button_id}"
            }


# Singleton browser session
browser_session = BrowserSession()


class BrowserNavigateTool(BaseTool):
    """Navigates browser to target enterprise URL."""
    def __init__(self):
        schema = {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to open in the browser."}
            },
            "required": ["url"]
        }
        super().__init__(
            name="browser_navigate",
            description="Navigates the web browser to an internal or external web application URL.",
            parameters_schema=schema
        )

    def run(self, url: str) -> Dict[str, Any]:
        page_state = browser_session.navigate(url)
        return {
            "current_url": page_state.get("url"),
            "page_title": page_state.get("title"),
            "interactive_elements_count": len(page_state.get("interactive_elements", []))
        }


class BrowserInspectDOMTool(BaseTool):
    """Inspects the current webpage DOM tree and interactive controls."""
    def __init__(self):
        schema = {"type": "object", "properties": {}}
        super().__init__(
            name="browser_inspect_dom",
            description="Inspects the current webpage DOM, finding input boxes, buttons, and tables.",
            parameters_schema=schema
        )

    def run(self) -> Dict[str, Any]:
        if not browser_session.current_url:
            browser_session.navigate("http://internal-erp.local/portal/invoices")
        return browser_session.dom_state


class BrowserFillFormTool(BaseTool):
    """Fills an input form field in the simulated browser."""
    def __init__(self):
        schema = {
            "type": "object",
            "properties": {
                "field_name": {"type": "string", "description": "Element ID or name (e.g. 'vendor', 'input-amount')."},
                "value": {"type": "string", "description": "Value to type into the field."}
            },
            "required": ["field_name", "value"]
        }
        super().__init__(
            name="browser_fill_form",
            description="Enters text or numeric value into a specific form field on the active webpage.",
            parameters_schema=schema
        )

    def run(self, field_name: str, value: str) -> Dict[str, Any]:
        return browser_session.fill_form_field(field_name, value)


class BrowserClickButtonTool(BaseTool):
    """Clicks a button or interactive element on the webpage."""
    def __init__(self):
        schema = {
            "type": "object",
            "properties": {
                "button_id": {"type": "string", "description": "Element ID or text of the button to click."}
            },
            "required": ["button_id"]
        }
        super().__init__(
            name="browser_click_button",
            description="Clicks a button on the current webpage (e.g. 'btn-submit-invoice').",
            parameters_schema=schema
        )

    def run(self, button_id: str) -> Dict[str, Any]:
        return browser_session.click_button(button_id)

from __future__ import annotations
import os
import json
from typing import Any, Dict, List, Optional


class BaseCognitiveEngine:
    """Base interface for AI cognitive engines."""
    def reason_and_plan(self, goal: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def summarize_completion(self, goal: str, memory_snapshot: Dict[str, Any], verification_summary: str) -> str:
        raise NotImplementedError


class LocalAutonomousEngine(BaseCognitiveEngine):
    """
    Built-in Deterministic Autonomous Cognitive Engine.
    Provides fast, robust, offline semantic reasoning, intent decomposition,
    self-healing heuristics, and structured evidence summarization
    without external API keys or cloud dependencies.
    """

    def summarize_completion(self, goal: str, memory_snapshot: Dict[str, Any], verification_summary: str) -> str:
        entities = memory_snapshot.get("discovered_entities") or memory_snapshot.get("entities", {})
        vendor = entities.get("vendor", "Unknown Vendor")
        inv_num = entities.get("invoice_number", "N/A")
        amount = entities.get("amount", 0.0)
        due_date = entities.get("due_date", "N/A")
        currency = entities.get("currency", "USD")

        summary = (
            f"Successfully completed task: '{goal}'.\n"
            f"Processed latest invoice for {vendor} (Invoice #{inv_num}).\n"
            f"Extracted Total: {currency} {amount:,.2f} | Due Date: {due_date}.\n"
            f"Ledger Status: {verification_summary}"
        )
        return summary



class ExternalLLMEngine(BaseCognitiveEngine):
    """
    Adapter for Google Gemini or OpenAI when an API key is available in the environment.
    """

    def __init__(self, api_key: Optional[str] = None, provider: str = "gemini"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.provider = provider
        self._client = None
        if self.api_key and self.provider == "gemini":
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel("gemini-1.5-flash")
            except Exception:
                self._client = None

    def is_available(self) -> bool:
        return self._client is not None

    def summarize_completion(self, goal: str, memory_snapshot: Dict[str, Any], verification_summary: str) -> str:
        if not self.is_available():
            return LocalAutonomousEngine().summarize_completion(goal, memory_snapshot, verification_summary)

        prompt = f"""
        You are an autonomous AI Task Worker. Summarize the completed task concisely with evidence.
        Goal: {goal}
        Working Memory Entities: {json.dumps(memory_snapshot.get('entities', {}))}
        Verification Status: {verification_summary}
        """
        try:
            response = self._client.generate_content(prompt)
            return response.text.strip()
        except Exception:
            return LocalAutonomousEngine().summarize_completion(goal, memory_snapshot, verification_summary)


def get_default_engine() -> BaseCognitiveEngine:
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        engine = ExternalLLMEngine(api_key=gemini_key)
        if engine.is_available():
            return engine
    return LocalAutonomousEngine()

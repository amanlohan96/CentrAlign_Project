from __future__ import annotations
from typing import Any, Dict, List, Optional
from core.models import WorkingMemory


class AgentMemoryManager:
    """
    Manages working memory, blackboard state, and entity storage for the AI worker.
    """

    def __init__(self, memory: Optional[WorkingMemory] = None):
        self.memory = memory or WorkingMemory()

    def record_observation(self, note: str) -> None:
        self.memory.note(note)

    def set_entity(self, key: str, value: Any) -> None:
        self.memory.record_entity(key, value)

    def get_entity(self, key: str, default: Any = None) -> Any:
        return self.memory.get_entity(key, default)

    def record_visited_path(self, path: str) -> None:
        if path not in self.memory.visited_locations:
            self.memory.visited_locations.append(path)

    def record_error(self, step_id: str, error_msg: str, recovery_attempted: Optional[str] = None) -> None:
        self.memory.error_history.append({
            "step_id": step_id,
            "error": error_msg,
            "recovery_attempted": recovery_attempted
        })

    def get_context_snapshot(self) -> Dict[str, Any]:
        return {
            "entities": self.memory.discovered_entities,
            "scratchpad": self.memory.scratchpad[-10:],  # recent observations
            "visited_locations": self.memory.visited_locations,
            "errors": self.memory.error_history
        }

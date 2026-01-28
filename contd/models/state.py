from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


def utcnow():
    return datetime.utcnow()


@dataclass(frozen=True)
class WorkflowState:
    workflow_id: str
    step_number: int
    variables: Dict[str, Any]  # User state
    metadata: Dict[str, Any]  # System metadata
    version: str  # Schema version
    checksum: str  # Integrity check
    org_id: Optional[str] = None  # Added for multi-tenancy

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return WorkflowState(**d)


class StateMigration:
    @staticmethod
    def migrate(state: dict, from_version: str) -> dict:
        """Apply all migrations from from_version to current"""
        migrations = [
            ("1.0", "1.1", StateMigration._v1_to_v1_1),
            ("1.1", "1.2", StateMigration._v1_1_to_v1_2),
        ]

        current = from_version
        for from_v, to_v, migrator in migrations:
            if current == from_v:
                state = migrator(state)
                state["version"] = to_v
                current = to_v

        return state

    @staticmethod
    def _v1_to_v1_1(state: dict) -> dict:
        # Example: Add new required field
        state.setdefault("metadata", {})
        state["metadata"]["migrated_at"] = utcnow().isoformat()
        return state

    @staticmethod
    def _v1_1_to_v1_2(state: dict) -> dict:
        # Placeholder for 1.2
        return state

import json
from dataclasses import asdict
from typing import Any, Dict, List
import jsonpatch
from .state import WorkflowState


def serialize(obj: Any) -> str:
    """Serialize object to JSON string."""
    if hasattr(obj, "__dataclass_fields__"):
        return json.dumps(asdict(obj), default=str, sort_keys=True)
    return json.dumps(obj, default=str, sort_keys=True)


def deserialize(data: str, cls=None) -> Any:
    """Deserialize JSON string."""
    d = json.loads(data)
    if cls is WorkflowState:
        return WorkflowState(**d)
    return d


def compute_delta(old_state: dict, new_state: dict) -> List[Dict[str, Any]]:
    """
    Compute minimal JSON Patch between states
    """
    # Assuming states are dicts or convertable to dicts
    if hasattr(old_state, "to_dict"):
        old_state = old_state.to_dict()
    if hasattr(new_state, "to_dict"):
        new_state = new_state.to_dict()

    patch = jsonpatch.make_patch(old_state, new_state)
    return patch.patch  # List of operations


def apply_delta(state: WorkflowState, delta: List[Dict[str, Any]]) -> WorkflowState:
    """
    Apply JSON Patch (RFC 6902) operations to WorkflowState
    """
    state_dict = asdict(state)
    patched = jsonpatch.apply_patch(state_dict, delta)

    # Reconstruct WorkflowState from patched dict
    # Ensure nested classes are handled if necessary, but WorkflowState seems flat-ish in current def
    return WorkflowState(**patched)

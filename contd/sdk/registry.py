from typing import Callable, Dict, Optional


class WorkflowRegistry:
    _workflows: Dict[str, Callable] = {}

    @classmethod
    def register(cls, name: str, fn: Callable):
        cls._workflows[name] = fn

    @classmethod
    def get(cls, name: str) -> Optional[Callable]:
        return cls._workflows.get(name)

    @classmethod
    def list_all(cls) -> Dict[str, Callable]:
        return cls._workflows.copy()

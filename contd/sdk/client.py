from typing import Optional, Dict, List
import requests
from dataclasses import dataclass
from .decorators import WorkflowConfig
from contd.models.savepoint import Savepoint

class ContdClient:
    """Client for remote workflow execution"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.contd.ai"):
        self.api_key = api_key
        self.base_url = base_url
    
    def start_workflow(
        self,
        workflow_name: str,
        input_data: dict,
        config: WorkflowConfig | None = None
    ) -> str:
        """Start workflow remotely, returns workflow_id"""
        # config.to_dict doesn't exist on dataclass unless we use asdict
        from dataclasses import asdict
        cfg_dict = asdict(config) if config else None
        
        response = requests.post(
            f"{self.base_url}/v1/workflows",
            json={
                "workflow_name": workflow_name,
                "input": input_data,
                "config": cfg_dict
            },
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        response.raise_for_status()
        return response.json()["workflow_id"]
    
    def get_status(self, workflow_id: str) -> dict:
        """Get workflow status"""
        response = requests.get(
            f"{self.base_url}/v1/workflows/{workflow_id}",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        response.raise_for_status()
        return response.json()
    
    def resume(self, workflow_id: str) -> str:
        """Resume interrupted workflow"""
        response = requests.post(
            f"{self.base_url}/v1/workflows/{workflow_id}/resume",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        response.raise_for_status()
        return response.json()["status"]
    
    def get_savepoints(self, workflow_id: str) -> List[Savepoint]:
        """Get all savepoints for workflow"""
        response = requests.get(
            f"{self.base_url}/v1/workflows/{workflow_id}/savepoints",
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        response.raise_for_status()
        # deserialization needs care for Savepoint fields
        # returning dicts or objects? Spec says Savepoint objects.
        # Assuming response matches Savepoint fields exactly
        return [Savepoint(**sp) for sp in response.json().get("savepoints", [])]
    
    def time_travel(self, workflow_id: str, savepoint_id: str) -> str:
        """Restore workflow to specific savepoint"""
        response = requests.post(
            f"{self.base_url}/v1/workflows/{workflow_id}/time-travel",
            json={"savepoint_id": savepoint_id},
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        response.raise_for_status()
        return response.json()["new_workflow_id"]

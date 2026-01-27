"""
CLI Configuration management.
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any

DEFAULT_CONFIG_FILE = "contd.json"
DEFAULT_CONFIG_DIR = ".contd"


@dataclass
class ContdConfig:
    """Configuration for contd CLI and runtime."""
    # Storage backend
    storage_backend: str = "sqlite"  # sqlite, postgres, redis
    
    # SQLite settings (default for local dev)
    sqlite_path: str = ".contd/contd.db"
    
    # Postgres settings
    postgres_host: Optional[str] = None
    postgres_port: int = 5432
    postgres_database: Optional[str] = None
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None
    
    # Redis settings
    redis_url: Optional[str] = None
    
    # S3 settings (for large snapshots)
    s3_bucket: Optional[str] = None
    s3_prefix: str = "contd/"
    s3_region: Optional[str] = None
    
    # Runtime settings
    snapshot_interval: int = 10
    lease_ttl_seconds: int = 30
    heartbeat_interval_seconds: int = 10
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json, text
    
    # Organization (multi-tenancy)
    org_id: str = "default"
    
    # Workflow discovery
    workflow_modules: list = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContdConfig":
        # Filter to only known fields
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)


def find_config_file(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    Find contd.json config file by walking up directory tree.
    """
    current = start_path or Path.cwd()
    
    while current != current.parent:
        config_path = current / DEFAULT_CONFIG_FILE
        if config_path.exists():
            return config_path
        current = current.parent
    
    # Check home directory
    home_config = Path.home() / DEFAULT_CONFIG_DIR / DEFAULT_CONFIG_FILE
    if home_config.exists():
        return home_config
    
    return None


def load_config(config_path: Optional[Path] = None) -> ContdConfig:
    """
    Load configuration from file or use defaults.
    """
    if config_path is None:
        config_path = find_config_file()
    
    if config_path and config_path.exists():
        with open(config_path) as f:
            data = json.load(f)
        return ContdConfig.from_dict(data)
    
    return ContdConfig()


def save_config(config: ContdConfig, config_path: Path):
    """
    Save configuration to file.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config.to_dict(), f, indent=2)


def init_project(path: Path, config: Optional[ContdConfig] = None) -> Path:
    """
    Initialize a new contd project.
    
    Creates:
    - contd.json config file
    - .contd/ directory for local storage
    """
    config = config or ContdConfig()
    
    # Create .contd directory
    contd_dir = path / DEFAULT_CONFIG_DIR
    contd_dir.mkdir(parents=True, exist_ok=True)
    
    # Create config file
    config_path = path / DEFAULT_CONFIG_FILE
    save_config(config, config_path)
    
    return config_path

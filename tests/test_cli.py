"""
Tests for the contd CLI.
"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from click.testing import CliRunner

from contd.cli.main import cli
from contd.cli.config import ContdConfig, init_project, load_config, save_config


class TestConfig:
    """Tests for CLI configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ContdConfig()
        assert config.storage_backend == "sqlite"
        assert config.sqlite_path == ".contd/contd.db"
        assert config.org_id == "default"
        assert config.log_level == "INFO"
    
    def test_config_to_dict(self):
        """Test config serialization."""
        config = ContdConfig(storage_backend="postgres", org_id="test-org")
        data = config.to_dict()
        assert data["storage_backend"] == "postgres"
        assert data["org_id"] == "test-org"
    
    def test_config_from_dict(self):
        """Test config deserialization."""
        data = {
            "storage_backend": "redis",
            "redis_url": "redis://localhost:6379",
            "org_id": "my-org"
        }
        config = ContdConfig.from_dict(data)
        assert config.storage_backend == "redis"
        assert config.redis_url == "redis://localhost:6379"
        assert config.org_id == "my-org"
    
    def test_config_from_dict_ignores_unknown(self):
        """Test that unknown fields are ignored."""
        data = {
            "storage_backend": "sqlite",
            "unknown_field": "value",
            "another_unknown": 123
        }
        config = ContdConfig.from_dict(data)
        assert config.storage_backend == "sqlite"
        assert not hasattr(config, "unknown_field")
    
    def test_save_and_load_config(self):
        """Test saving and loading config from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "contd.json"
            
            original = ContdConfig(
                storage_backend="postgres",
                postgres_host="db.example.com",
                org_id="test-org"
            )
            save_config(original, config_path)
            
            loaded = load_config(config_path)
            assert loaded.storage_backend == "postgres"
            assert loaded.postgres_host == "db.example.com"
            assert loaded.org_id == "test-org"
    
    def test_init_project(self):
        """Test project initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            config_path = init_project(project_path)
            
            assert config_path.exists()
            assert (project_path / ".contd").is_dir()
            
            config = load_config(config_path)
            assert config.storage_backend == "sqlite"


class TestInitCommand:
    """Tests for 'contd init' command."""
    
    def test_init_creates_config(self):
        """Test that init creates config file."""
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['init'])
            
            assert result.exit_code == 0
            assert Path("contd.json").exists()
            assert Path(".contd").is_dir()
            assert "Initialized contd project" in result.output
    
    def test_init_with_backend(self):
        """Test init with specific backend."""
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ['init', '--backend', 'postgres'])
            
            assert result.exit_code == 0
            
            with open("contd.json") as f:
                config = json.load(f)
            assert config["storage_backend"] == "postgres"
    
    def test_init_refuses_overwrite(self):
        """Test that init won't overwrite existing config."""
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            # Create existing config
            Path("contd.json").write_text('{"storage_backend": "redis"}')
            
            result = runner.invoke(cli, ['init'])
            
            assert "already exists" in result.output
            
            # Original config unchanged
            with open("contd.json") as f:
                config = json.load(f)
            assert config["storage_backend"] == "redis"
    
    def test_init_force_overwrites(self):
        """Test that init --force overwrites existing config."""
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            # Create existing config
            Path("contd.json").write_text('{"storage_backend": "redis"}')
            
            result = runner.invoke(cli, ['init', '--force'])
            
            assert result.exit_code == 0
            
            with open("contd.json") as f:
                config = json.load(f)
            assert config["storage_backend"] == "sqlite"


class TestStatusCommand:
    """Tests for 'contd status' command."""
    
    @patch('contd.cli.main.get_engine')
    def test_status_not_found(self, mock_get_engine):
        """Test status for non-existent workflow."""
        mock_engine = Mock()
        mock_engine.get_workflow_status.return_value = {
            "workflow_id": "wf-123",
            "org_id": "default",
            "event_count": 0,
            "snapshot_count": 0,
            "has_lease": False
        }
        mock_get_engine.return_value = mock_engine
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("contd.json").write_text('{}')
            result = runner.invoke(cli, ['status', 'wf-123'])
            
            assert "NOT FOUND" in result.output
    
    @patch('contd.cli.main.get_engine')
    def test_status_running(self, mock_get_engine):
        """Test status for running workflow."""
        mock_engine = Mock()
        mock_engine.get_workflow_status.return_value = {
            "workflow_id": "wf-123",
            "org_id": "default",
            "event_count": 10,
            "snapshot_count": 2,
            "has_lease": True,
            "lease_owner": "worker-1",
            "lease_expires": "2024-01-15T10:30:00"
        }
        mock_get_engine.return_value = mock_engine
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("contd.json").write_text('{}')
            result = runner.invoke(cli, ['status', 'wf-123'])
            
            assert "RUNNING" in result.output
            assert "worker-1" in result.output
    
    @patch('contd.cli.main.get_engine')
    def test_status_suspended(self, mock_get_engine):
        """Test status for suspended workflow."""
        mock_engine = Mock()
        mock_engine.get_workflow_status.return_value = {
            "workflow_id": "wf-123",
            "org_id": "default",
            "event_count": 5,
            "snapshot_count": 1,
            "has_lease": False,
            "latest_snapshot_step": 3
        }
        mock_get_engine.return_value = mock_engine
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("contd.json").write_text('{}')
            result = runner.invoke(cli, ['status', 'wf-123'])
            
            assert "SUSPENDED" in result.output


class TestInspectCommand:
    """Tests for 'contd inspect' command."""
    
    @patch('contd.cli.main.get_engine')
    def test_inspect_shows_state(self, mock_get_engine):
        """Test inspect shows workflow state."""
        from contd.models.state import WorkflowState
        
        mock_engine = Mock()
        mock_engine.get_workflow_status.return_value = {
            "workflow_id": "wf-123",
            "event_count": 5
        }
        mock_engine.restore.return_value = (
            WorkflowState(
                workflow_id="wf-123",
                step_number=3,
                variables={"key": "value"},
                metadata={},
                version="1.0",
                checksum="abc",
                org_id="default"
            ),
            5
        )
        mock_engine.snapshots.list_snapshots.return_value = [
            {"snapshot_id": "snap-1", "step_number": 3, "last_event_seq": 5, "created_at": "2024-01-15"}
        ]
        mock_get_engine.return_value = mock_engine
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("contd.json").write_text('{}')
            result = runner.invoke(cli, ['inspect', 'wf-123'])
            
            assert result.exit_code == 0
            assert "Step: 3" in result.output
            assert "snap-1" in result.output


class TestTimeTravelCommand:
    """Tests for 'contd time-travel' command."""
    
    @patch('contd.cli.main.get_engine')
    def test_time_travel_dry_run(self, mock_get_engine):
        """Test time-travel dry run."""
        from contd.models.state import WorkflowState
        
        mock_engine = Mock()
        mock_engine.snapshots.load.return_value = WorkflowState(
            workflow_id="wf-123",
            step_number=5,
            variables={"x": 1},
            metadata={},
            version="1.0",
            checksum="abc",
            org_id="default"
        )
        mock_get_engine.return_value = mock_engine
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("contd.json").write_text('{}')
            result = runner.invoke(cli, ['time-travel', 'wf-123', 'snap-abc', '--dry-run'])
            
            assert result.exit_code == 0
            assert "DRY RUN" in result.output
            assert "Step: 5" in result.output
    
    @patch('contd.cli.main.get_engine')
    def test_time_travel_creates_new_workflow(self, mock_get_engine):
        """Test time-travel creates new workflow."""
        from contd.models.state import WorkflowState
        
        mock_engine = Mock()
        mock_engine.snapshots.load.return_value = WorkflowState(
            workflow_id="wf-123",
            step_number=5,
            variables={"x": 1},
            metadata={},
            version="1.0",
            checksum="abc",
            org_id="default"
        )
        mock_engine.snapshots.save.return_value = "new-snap-id"
        mock_get_engine.return_value = mock_engine
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("contd.json").write_text('{}')
            result = runner.invoke(cli, ['time-travel', 'wf-123', 'snap-abc'])
            
            assert result.exit_code == 0
            assert "Created new workflow" in result.output
            assert "wf-123-tt-" in result.output


class TestLogsCommand:
    """Tests for 'contd logs' command."""
    
    @patch('contd.cli.main.get_engine')
    def test_logs_shows_events(self, mock_get_engine):
        """Test logs shows workflow events."""
        from contd.models.events import StepCompletedEvent, EventType
        from datetime import datetime
        
        mock_engine = Mock()
        mock_engine.journal.get_events.return_value = [
            Mock(
                event_id="evt-1",
                event_type=EventType.STEP_COMPLETED,
                timestamp=datetime(2024, 1, 15, 10, 30),
                step_id="step_0",
                step_name="process_data",
                duration_ms=150
            )
        ]
        mock_get_engine.return_value = mock_engine
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("contd.json").write_text('{}')
            result = runner.invoke(cli, ['logs', 'wf-123'])
            
            assert result.exit_code == 0
            assert "process_data" in result.output
            assert "150ms" in result.output
    
    @patch('contd.cli.main.get_engine')
    def test_logs_no_events(self, mock_get_engine):
        """Test logs with no events."""
        mock_engine = Mock()
        mock_engine.journal.get_events.return_value = []
        mock_get_engine.return_value = mock_engine
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("contd.json").write_text('{}')
            result = runner.invoke(cli, ['logs', 'wf-123'])
            
            assert "No logs found" in result.output


class TestRunCommand:
    """Tests for 'contd run' command."""
    
    @patch('contd.cli.main.get_engine')
    @patch('contd.cli.main.load_workflow_modules')
    def test_run_workflow_not_found(self, mock_load, mock_get_engine):
        """Test run with non-existent workflow."""
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            Path("contd.json").write_text('{}')
            result = runner.invoke(cli, ['run', 'nonexistent'])
            
            assert result.exit_code == 1
            assert "not found" in result.output
    
    @patch('contd.cli.main.get_engine')
    @patch('contd.cli.main.load_workflow_modules')
    @patch('contd.sdk.registry.WorkflowRegistry.get')
    def test_run_with_input(self, mock_registry_get, mock_load, mock_get_engine):
        """Test run with JSON input."""
        mock_workflow = Mock(return_value={"result": "success"})
        mock_registry_get.return_value = mock_workflow
        mock_get_engine.return_value = Mock()
        
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            Path("contd.json").write_text('{}')
            result = runner.invoke(cli, ['run', 'my_workflow', '--input', '{"key": "value"}'])
            
            assert result.exit_code == 0
            mock_workflow.assert_called_once_with(key="value")


class TestListCommand:
    """Tests for 'contd list' command."""
    
    @patch('contd.cli.main.get_engine')
    def test_list_empty(self, mock_get_engine):
        """Test list with no workflows."""
        mock_engine = Mock()
        mock_engine.db.query.return_value = []
        mock_get_engine.return_value = mock_engine
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("contd.json").write_text('{}')
            result = runner.invoke(cli, ['list'])
            
            assert "No workflows found" in result.output
    
    @patch('contd.cli.main.get_engine')
    def test_list_shows_workflows(self, mock_get_engine):
        """Test list shows workflows."""
        mock_engine = Mock()
        mock_engine.db.query.return_value = [
            {"workflow_id": "wf-1", "last_activity": "2024-01-15"},
            {"workflow_id": "wf-2", "last_activity": "2024-01-14"}
        ]
        mock_engine.get_workflow_status.return_value = {
            "has_lease": False,
            "event_count": 5
        }
        mock_get_engine.return_value = mock_engine
        
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("contd.json").write_text('{}')
            result = runner.invoke(cli, ['list'])
            
            assert "wf-1" in result.output
            assert "wf-2" in result.output

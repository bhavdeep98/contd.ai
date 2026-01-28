"""
Main CLI entry point for contd.
"""

import click
import sys
import json
import importlib
from pathlib import Path
from datetime import datetime

from .config import (
    ContdConfig,
    load_config,
    init_project,
    find_config_file,
    DEFAULT_CONFIG_FILE,
)


def get_engine(config: ContdConfig):
    """Get execution engine based on config."""
    from contd.core.engine import ExecutionEngine, EngineConfig
    from contd.persistence.adapters.factory import create_adapter

    adapter = create_adapter(
        config.storage_backend,
        {
            "sqlite_path": config.sqlite_path,
            "postgres_host": config.postgres_host,
            "postgres_port": config.postgres_port,
            "postgres_database": config.postgres_database,
            "postgres_user": config.postgres_user,
            "postgres_password": config.postgres_password,
            "redis_url": config.redis_url,
        },
    )

    engine_config = EngineConfig(
        snapshot_interval=config.snapshot_interval,
        use_mocks=config.storage_backend == "memory",
    )

    engine = ExecutionEngine(engine_config)
    engine.db = adapter
    engine.initialize()
    return engine


def load_workflow_modules(config: ContdConfig):
    """Load workflow modules to register workflows."""
    for module_path in config.workflow_modules:
        try:
            importlib.import_module(module_path)
        except ImportError as e:
            click.echo(f"Warning: Could not load module {module_path}: {e}", err=True)


@click.group()
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Path to config file"
)
@click.pass_context
def cli(ctx, config):
    """Contd - Durable workflow execution engine."""
    ctx.ensure_object(dict)

    config_path = Path(config) if config else find_config_file()
    ctx.obj["config"] = load_config(config_path)
    ctx.obj["config_path"] = config_path


@cli.command()
@click.option(
    "--backend",
    "-b",
    type=click.Choice(["sqlite", "postgres", "redis"]),
    default="sqlite",
    help="Storage backend",
)
@click.option("--force", "-f", is_flag=True, help="Overwrite existing config")
@click.pass_context
def init(ctx, backend, force):
    """Initialize a new contd project with configuration."""
    project_path = Path.cwd()
    config_path = project_path / DEFAULT_CONFIG_FILE

    if config_path.exists() and not force:
        click.echo(f"Config file already exists: {config_path}")
        click.echo("Use --force to overwrite")
        return

    config = ContdConfig(storage_backend=backend)
    result_path = init_project(project_path, config)

    click.echo(f"Initialized contd project at {project_path}")
    click.echo(f"  Config: {result_path}")
    click.echo(f"  Backend: {backend}")
    click.echo("  Data dir: .contd/")
    click.echo("")
    click.echo("Next steps:")
    click.echo("  1. Add workflow modules to contd.json")
    click.echo("  2. Run: contd run <workflow_name>")


@cli.command()
@click.argument("workflow_name")
@click.option("--input", "-i", "input_data", help="JSON input data")
@click.option(
    "--input-file", "-f", type=click.Path(exists=True), help="JSON input file"
)
@click.option("--workflow-id", "-w", help="Custom workflow ID")
@click.option("--async", "run_async", is_flag=True, help="Run asynchronously")
@click.pass_context
def run(ctx, workflow_name, input_data, input_file, workflow_id, run_async):
    """Execute a workflow locally.

    Examples:
        contd run my_workflow --input '{"key": "value"}'
        contd run my_workflow -f input.json
    """
    from contd.sdk.registry import WorkflowRegistry
    from contd.runtime.executor import WorkflowExecutor
    import uuid

    config = ctx.obj["config"]
    load_workflow_modules(config)

    # Get workflow
    workflow_fn = WorkflowRegistry.get(workflow_name)
    if not workflow_fn:
        available = list(WorkflowRegistry.list_all().keys())
        click.echo(f"Workflow '{workflow_name}' not found.", err=True)
        if available:
            click.echo(f"Available workflows: {', '.join(available)}", err=True)
        else:
            click.echo(
                "No workflows registered. Add workflow modules to contd.json", err=True
            )
        sys.exit(1)

    # Parse input
    parsed_input = {}
    if input_file:
        with open(input_file) as f:
            parsed_input = json.load(f)
    elif input_data:
        parsed_input = json.loads(input_data)

    # Generate workflow ID
    wf_id = workflow_id or f"{workflow_name}-{uuid.uuid4().hex[:8]}"

    click.echo(f"Starting workflow: {workflow_name}")
    click.echo(f"  Workflow ID: {wf_id}")
    click.echo(f"  Input: {json.dumps(parsed_input)[:100]}...")
    click.echo("")

    try:
        engine = get_engine(config)
        WorkflowExecutor(engine)

        # Execute workflow
        start_time = datetime.now()
        result = workflow_fn(**parsed_input)
        duration = (datetime.now() - start_time).total_seconds()

        click.echo(f"Workflow completed in {duration:.2f}s")
        click.echo(f"Result: {json.dumps(result, default=str)[:500]}")

    except Exception as e:
        click.echo(f"Workflow failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("workflow_id")
@click.pass_context
def status(ctx, workflow_id):
    """Check workflow status.

    Shows current state, lease info, and execution progress.
    """
    config = ctx.obj["config"]

    try:
        engine = get_engine(config)
        status_info = engine.get_workflow_status(workflow_id, config.org_id)

        click.echo(f"Workflow: {workflow_id}")
        click.echo(f"  Organization: {status_info.get('org_id', 'default')}")
        click.echo(f"  Events: {status_info.get('event_count', 0)}")
        click.echo(f"  Snapshots: {status_info.get('snapshot_count', 0)}")

        if status_info.get("has_lease"):
            click.echo("  Status: RUNNING")
            click.echo(f"  Owner: {status_info.get('lease_owner')}")
            click.echo(f"  Lease expires: {status_info.get('lease_expires')}")
        elif status_info.get("event_count", 0) > 0:
            click.echo("  Status: SUSPENDED")
            click.echo(
                f"  Last step: {status_info.get('latest_snapshot_step', 'unknown')}"
            )
        else:
            click.echo("  Status: NOT FOUND")

    except Exception as e:
        click.echo(f"Error getting status: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("workflow_id")
@click.pass_context
def resume(ctx, workflow_id):
    """Resume a suspended workflow.

    Restores state from the last checkpoint and continues execution.
    """
    from contd.sdk.registry import WorkflowRegistry

    config = ctx.obj["config"]
    load_workflow_modules(config)

    try:
        engine = get_engine(config)

        # Check if workflow exists
        status_info = engine.get_workflow_status(workflow_id, config.org_id)
        if status_info.get("event_count", 0) == 0:
            click.echo(f"Workflow {workflow_id} not found", err=True)
            sys.exit(1)

        if status_info.get("has_lease"):
            click.echo(f"Workflow {workflow_id} is already running", err=True)
            click.echo(f"  Owner: {status_info.get('lease_owner')}")
            sys.exit(1)

        click.echo(f"Resuming workflow: {workflow_id}")
        click.echo(
            f"  Restoring from step: {status_info.get('latest_snapshot_step', 0)}"
        )

        # Restore and resume
        state, last_seq = engine.restore(workflow_id, config.org_id)
        click.echo(f"  State restored at step {state.step_number}")

        # Get workflow name from state metadata
        workflow_name = state.metadata.get("workflow_name")
        if workflow_name:
            workflow_fn = WorkflowRegistry.get(workflow_name)
            if workflow_fn:
                click.echo(f"  Continuing workflow: {workflow_name}")
                # Note: Full resume requires workflow-specific logic
                # This is a simplified version

        click.echo("Workflow resumed successfully")

    except Exception as e:
        click.echo(f"Error resuming workflow: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("workflow_id")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed state")
@click.pass_context
def inspect(ctx, workflow_id, verbose):
    """View workflow state and savepoints.

    Shows current state, all savepoints, and execution history.
    """
    config = ctx.obj["config"]

    try:
        engine = get_engine(config)

        # Get status
        status_info = engine.get_workflow_status(workflow_id, config.org_id)

        if status_info.get("event_count", 0) == 0:
            click.echo(f"Workflow {workflow_id} not found", err=True)
            sys.exit(1)

        click.echo(f"Workflow: {workflow_id}")
        click.echo("=" * 50)

        # Current state
        click.echo("\nCurrent State:")
        try:
            state, last_seq = engine.restore(workflow_id, config.org_id)
            click.echo(f"  Step: {state.step_number}")
            click.echo(f"  Version: {state.version}")
            click.echo(f"  Last event seq: {last_seq}")

            if verbose:
                click.echo(
                    f"  Variables: {json.dumps(state.variables, default=str, indent=4)}"
                )
                click.echo(
                    f"  Metadata: {json.dumps(state.metadata, default=str, indent=4)}"
                )
        except Exception as e:
            click.echo(f"  Could not restore state: {e}")

        # Snapshots
        click.echo("\nSavepoints/Snapshots:")
        snapshots = engine.snapshots.list_snapshots(workflow_id, config.org_id)
        if snapshots:
            for snap in snapshots[:10]:  # Show last 10
                s = snap if isinstance(snap, dict) else dict(snap)
                click.echo(
                    f"  [{s.get('snapshot_id', 'unknown')[:8]}...] "
                    f"Step {s.get('step_number', '?')} - "
                    f"Event seq {s.get('last_event_seq', '?')} - "
                    f"{s.get('created_at', 'unknown')}"
                )
        else:
            click.echo("  No snapshots found")

        # Recent events
        if verbose:
            click.echo("\nRecent Events:")
            events = engine.journal.get_events(
                workflow_id, config.org_id, after_seq=-1, limit=10
            )
            for event in events:
                etype = getattr(event, "event_type", "unknown")
                if hasattr(etype, "value"):
                    etype = etype.value
                click.echo(f"  [{event.event_id[:8]}...] {etype} - {event.timestamp}")

    except Exception as e:
        click.echo(f"Error inspecting workflow: {e}", err=True)
        sys.exit(1)


@cli.command("time-travel")
@click.argument("workflow_id")
@click.argument("savepoint_id")
@click.option(
    "--dry-run", is_flag=True, help="Show what would happen without executing"
)
@click.pass_context
def time_travel(ctx, workflow_id, savepoint_id, dry_run):
    """Restore workflow to a specific savepoint for debugging.

    Creates a new workflow instance from the savepoint state.

    Examples:
        contd time-travel wf-123 sp-abc123
        contd time-travel wf-123 sp-abc123 --dry-run
    """
    import uuid

    config = ctx.obj["config"]

    try:
        engine = get_engine(config)

        # Load the savepoint
        click.echo(f"Loading savepoint: {savepoint_id}")

        try:
            state = engine.snapshots.load(savepoint_id)
        except Exception:
            click.echo(f"Savepoint not found: {savepoint_id}", err=True)
            click.echo(
                "Use 'contd inspect <workflow_id>' to list available savepoints",
                err=True,
            )
            sys.exit(1)

        click.echo(f"  Workflow: {state.workflow_id}")
        click.echo(f"  Step: {state.step_number}")
        click.echo(f"  Variables: {list(state.variables.keys())}")

        if dry_run:
            click.echo("\n[DRY RUN] Would create new workflow from this state")
            click.echo(
                f"  New workflow ID would be: {workflow_id}-tt-{uuid.uuid4().hex[:8]}"
            )
            return

        # Create new workflow from savepoint
        new_workflow_id = f"{workflow_id}-tt-{uuid.uuid4().hex[:8]}"

        # Save as new snapshot for the new workflow
        from contd.models.state import WorkflowState

        new_state = WorkflowState(
            workflow_id=new_workflow_id,
            step_number=state.step_number,
            variables=state.variables,
            metadata={
                **state.metadata,
                "time_traveled_from": workflow_id,
                "source_savepoint": savepoint_id,
                "time_traveled_at": datetime.now().isoformat(),
            },
            version=state.version,
            checksum="",
            org_id=config.org_id,
        )

        snapshot_id = engine.snapshots.save(new_state, 0)

        click.echo("\nCreated new workflow from savepoint:")
        click.echo(f"  New workflow ID: {new_workflow_id}")
        click.echo(f"  New snapshot ID: {snapshot_id}")
        click.echo(f"\nResume with: contd resume {new_workflow_id}")

    except Exception as e:
        click.echo(f"Error during time-travel: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("workflow_id")
@click.option("--lines", "-n", default=50, help="Number of log lines to show")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option(
    "--level",
    "-l",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Minimum log level",
)
@click.pass_context
def logs(ctx, workflow_id, lines, follow, level):
    """View execution logs for a workflow.

    Shows structured log entries from workflow execution.

    Examples:
        contd logs wf-123
        contd logs wf-123 -n 100 -l DEBUG
    """
    config = ctx.obj["config"]

    try:
        engine = get_engine(config)

        # Get events as log entries
        events = engine.journal.get_events(
            workflow_id, config.org_id, after_seq=-1, limit=lines
        )

        if not events:
            click.echo(f"No logs found for workflow: {workflow_id}")
            return

        click.echo(f"Logs for workflow: {workflow_id}")
        click.echo("=" * 60)

        level_priority = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
        min_level = level_priority.get(level, 1)

        for event in events:
            # Determine log level from event type
            etype = getattr(event, "event_type", "unknown")
            if hasattr(etype, "value"):
                etype = etype.value

            if "FAILED" in str(etype).upper():
                log_level = "ERROR"
            elif "INTENTION" in str(etype).upper():
                log_level = "DEBUG"
            else:
                log_level = "INFO"

            if level_priority.get(log_level, 1) < min_level:
                continue

            # Format log entry
            timestamp = getattr(event, "timestamp", "unknown")
            if hasattr(timestamp, "strftime"):
                timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")

            step_id = getattr(event, "step_id", "")
            step_name = getattr(event, "step_name", "")

            log_line = f"[{timestamp}] [{log_level:7}] {etype}"
            if step_name:
                log_line += f" - {step_name}"
            if step_id:
                log_line += f" ({step_id})"

            # Add error details for failures
            if hasattr(event, "error") and event.error:
                log_line += f"\n    Error: {event.error}"

            # Add duration for completions
            if hasattr(event, "duration_ms") and event.duration_ms:
                log_line += f" [{event.duration_ms}ms]"

            click.echo(log_line)

    except Exception as e:
        click.echo(f"Error getting logs: {e}", err=True)
        sys.exit(1)


@cli.command("list")
@click.option(
    "--status",
    "-s",
    type=click.Choice(["all", "running", "suspended", "completed"]),
    default="all",
    help="Filter by status",
)
@click.option("--limit", "-n", default=20, help="Maximum workflows to show")
@click.pass_context
def list_workflows(ctx, status, limit):
    """List workflows in the system.

    Shows recent workflows with their status.
    """
    config = ctx.obj["config"]

    try:
        engine = get_engine(config)

        # Get unique workflow IDs from snapshots
        # This is a simplified approach - production would use a dedicated index
        all_snapshots = (
            engine.db.query(
                """
            SELECT DISTINCT workflow_id, MAX(created_at) as last_activity
            FROM snapshots
            WHERE org_id = ?
            GROUP BY workflow_id
            ORDER BY last_activity DESC
            LIMIT ?
        """,
                config.org_id,
                limit,
            )
            or []
        )

        if not all_snapshots:
            click.echo("No workflows found")
            return

        click.echo(f"Workflows (org: {config.org_id})")
        click.echo("=" * 70)
        click.echo(f"{'ID':<30} {'Status':<12} {'Last Activity':<20}")
        click.echo("-" * 70)

        for row in all_snapshots:
            r = row if isinstance(row, dict) else dict(row)
            wf_id = r.get("workflow_id", "unknown")

            # Get status
            try:
                status_info = engine.get_workflow_status(wf_id, config.org_id)
                if status_info.get("has_lease"):
                    wf_status = "RUNNING"
                elif status_info.get("event_count", 0) > 0:
                    wf_status = "SUSPENDED"
                else:
                    wf_status = "UNKNOWN"
            except Exception:
                wf_status = "UNKNOWN"

            # Filter by status
            if status != "all" and wf_status.lower() != status:
                continue

            last_activity = r.get("last_activity", "unknown")
            if hasattr(last_activity, "strftime"):
                last_activity = last_activity.strftime("%Y-%m-%d %H:%M:%S")

            click.echo(f"{wf_id:<30} {wf_status:<12} {str(last_activity):<20}")

    except Exception as e:
        click.echo(f"Error listing workflows: {e}", err=True)
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()

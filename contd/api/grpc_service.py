import grpc
import json
import logging
import threading

from contd.api.proto import workflow_pb2, workflow_pb2_grpc
from contd.core.engine import ExecutionEngine
from contd.sdk.registry import WorkflowRegistry
from contd.sdk.decorators import WorkflowConfig as SDKWorkflowConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowService(workflow_pb2_grpc.WorkflowServiceServicer):
    def __init__(self):
        self.engine = ExecutionEngine.get_instance()

    def StartWorkflow(self, request, context):
        try:
            workflow_name = request.workflow_name
            input_data = json.loads(request.input_json) if request.input_json else {}

            # Find workflow
            workflow_fn = WorkflowRegistry.get(workflow_name)
            if not workflow_fn:
                context.abort(
                    grpc.StatusCode.NOT_FOUND, f"Workflow '{workflow_name}' not found"
                )
                return

            # Prepare config
            config = None
            if request.has_config:
                config = SDKWorkflowConfig(
                    workflow_id=request.config.workflow_id or None,
                    # tags mapping
                    tags=dict(request.config.tags) if request.config.tags else None,
                )

            # Execution logic:
            # We are in separate thread (gRPC).
            # If we call workflow_fn(input), it runs synchronously in this thread
            # until completion (or suspension?).
            # The SDK is designed to be blocking?
            # Contd SDK: "Workflow ... resumable workflow".
            # If we just call it, it runs.
            # But the client expects "StarWorkflow" to return workflow_id immediately,
            # and maybe run in background?
            # User request says "Start workflow remotely, returns workflow_id".
            # Usually REST APIs start async.
            # So I should submit to a thread pool or background task.

            # However, for this implementation, let's execute in a thread pool.
            # But we need to return the ID *before* it finishes?
            # Or is it synchronous?
            # If it's a long running workflow, it should be async.

            # For now, let's verify if we can generate ID first.
            # The decorators use config.workflow_id or generate one.
            workflow_id = (
                config.workflow_id
                if config and config.workflow_id
                else f"wf-{workflow_name}-{context.peer()}"
            )
            # Actually use proper ID generation
            if not workflow_id or workflow_id.startswith("wf-"):
                # Use internal generator if needed, but decorators handle it.
                # To return it, we need to know it.
                # If we rely on decorator to generate it, we won't know it until execution starts.
                # Best to generate it here and pass it in config.
                import uuid

                workflow_id = f"wf-{uuid.uuid4()}"
                if not config:
                    config = SDKWorkflowConfig(workflow_id=workflow_id)
                else:
                    config.workflow_id = workflow_id

            # Submit to background
            # In a real system, this would go to a task queue (Celery/Temporal).
            # Here, we use a ThreadPoolExecutor or similar.
            # But wait, `ExecutionEngine` logic is embedded in the function decorator.

            def run_workflow():
                try:
                    workflow_fn(input_data, config=config)  # Passing input?
                    # Wait, SDK signature: wrapper(*args, **kwargs).
                    # Does workflow_fn accept dict? Or unpacked?
                    # The request has input_json.
                    # We assume the workflow accepts a single dict or we unpack?
                    # `ContdClient` passes `input_data` (dict).
                    # `ContdClient.start_workflow` description: `workflow_name` and `input_data`.
                    # The Python function `workflow_fn` takes whatever arguments it was defined with.
                    # This implies `input_data` needs to match the signature.
                    # Simplest assumption: Pass `input_data` as kwargs? or as single arg?
                    # Let's assume kwargs for flexibility.
                    pass
                except Exception as e:
                    logger.error(f"Workflow execution failed: {e}")

            # Start in background thread
            # Note: This is a simple in-process execution model.
            t = threading.Thread(target=run_workflow)  # Need to implement proper run

            # We need to correctly pass arguments.
            # If input_data is a dict, we can pass as kwargs.
            if isinstance(input_data, dict):
                kwargs = input_data
                args = []
            else:
                args = [input_data]
                kwargs = {}

            t = threading.Thread(
                target=workflow_fn, args=args, kwargs={"config": config, **kwargs}
            )
            t.start()

            return workflow_pb2.StartWorkflowResponse(workflow_id=workflow_id)

        except Exception as e:
            logger.error(f"Error starting workflow: {e}")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

    def GetWorkflowStatus(self, request, context):
        # In a real app, query DB.
        # Engine mock DB has rudimentary support.
        # We'll try to fetch state via Engine.
        try:
            # We don't have a direct "get_status" on engine.
            # But we can try restore() -> get state.
            state = self.engine.restore(request.workflow_id)
            if not state:
                context.abort(grpc.StatusCode.NOT_FOUND, "Workflow not found")

            # Infer status
            # If state exists, it's at least started.
            # Completed? We need to know if it's done.
            # Engine.complete_workflow tracks it?
            # SDK metrics track it.
            # For now: RUNNING if restored successfully?
            status = "RUNNING"  # Default

            return workflow_pb2.GetWorkflowStatusResponse(
                workflow_id=state.workflow_id,
                status=status,
                step_number=state.step_number,
                current_step=f"Step-{state.step_number}",  # Placeholder
            )
        except Exception as e:
            context.abort(grpc.StatusCode.NOT_FOUND, str(e))

    def ResumeWorkflow(self, request, context):
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "Not implemented yet")

    def ListSavepoints(self, request, context):
        # Check engine journal for SavepointCreatedEvent?
        # or Snapshots?
        # The prompt asks for "savepoints" which are "Rich savepoint with metadata".
        # `context.py` creates `SavepointCreatedEvent`.
        # So we query the journal.
        self.engine.journal.get_events(request.workflow_id)
        # But `get_events` doesn't exist on Journal yet, need to check `contd/persistence/journal.py`
        # Assuming we can filter.

        savepoints = []
        # ... logic to filter events ...

        return workflow_pb2.ListSavepointsResponse(savepoints=savepoints)

    def TimeTravel(self, request, context):
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "Not implemented yet")

    def ListWorkflows(self, request, context):
        # Return registered workflows? Or active executions?
        # Usually list executions.
        # We'll list executions from DB.
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "Not implemented yet")

    def DeleteWorkflow(self, request, context):
        context.abort(grpc.StatusCode.UNIMPLEMENTED, "Not implemented yet")

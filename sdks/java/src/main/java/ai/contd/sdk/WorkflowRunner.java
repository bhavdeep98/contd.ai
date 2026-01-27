package ai.contd.sdk;

import ai.contd.sdk.errors.*;
import ai.contd.sdk.types.*;

import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.*;
import java.util.function.Function;

/**
 * Executes workflows with the Contd runtime
 */
public class WorkflowRunner {
    private final Engine engine;
    private final WorkflowConfig config;

    public WorkflowRunner(Engine engine, WorkflowConfig config) {
        this.engine = engine;
        this.config = config != null ? config : new WorkflowConfig();
    }

    /**
     * Run a workflow function
     */
    public <T> T run(String workflowName, Function<Object, T> fn, Object input) {
        Instant startTime = Instant.now();

        // Create execution context
        ExecutionContext ctx = ExecutionContext.getOrCreate(
                config.getWorkflowId(),
                workflowName,
                config.getOrgId(),
                config.getTags()
        );
        ctx.setEngine(engine);

        // Acquire lease
        Lease lease = engine.getLeaseManager().acquire(ctx.getWorkflowId(), ctx.getExecutorId());
        if (lease == null) {
            throw new WorkflowLockedException(ctx.getWorkflowId());
        }
        ctx.setLease(lease);

        try {
            // Start heartbeat
            ctx.startHeartbeat(lease, engine);

            // Check if resuming
            if (ctx.isResuming()) {
                WorkflowState state = engine.restore(ctx.getWorkflowId());
                ctx.setState(state);
                System.out.println("Resumed workflow " + ctx.getWorkflowId() + " from step " + state.getStepNumber());
            }

            // Execute workflow
            T result = fn.apply(input);

            // Mark complete
            engine.completeWorkflow(ctx.getWorkflowId());

            Duration duration = Duration.between(startTime, Instant.now());
            System.out.println("Workflow " + ctx.getWorkflowId() + " completed in " + duration);

            return result;
        } finally {
            ctx.stopHeartbeat();
            engine.getLeaseManager().release(lease);
            ExecutionContext.clear();
        }
    }

    /**
     * Create a step runner
     */
    public StepRunner step(StepConfig config) {
        return new StepRunner(config);
    }

    /**
     * Step runner for executing steps within a workflow
     */
    public static class StepRunner {
        private final StepConfig config;

        public StepRunner(StepConfig config) {
            this.config = config != null ? config : new StepConfig();
        }

        /**
         * Run a step function
         */
        public <T> T run(String stepName, Callable<T> fn) throws Exception {
            ExecutionContext ctx = ExecutionContext.current();
            Engine engine = ctx.getEngine();
            if (engine == null) {
                throw new IllegalStateException("No execution engine in context");
            }

            Lease lease = ctx.getLease();
            String stepId = ctx.generateStepId(stepName);

            // Check idempotency
            WorkflowState cachedResult = engine.getIdempotency().checkCompleted(ctx.getWorkflowId(), stepId);
            if (cachedResult != null) {
                System.out.println("Step " + stepId + " already completed, returning cached result");
                ctx.setState(cachedResult);
                return null; // Cached result doesn't have the actual return value
            }

            // Allocate attempt
            int attemptId = engine.getIdempotency().allocateAttempt(ctx.getWorkflowId(), stepId, lease);

            // Write intention
            Map<String, Object> intentionEvent = new HashMap<>();
            intentionEvent.put("event_id", UUID.randomUUID().toString());
            intentionEvent.put("workflow_id", ctx.getWorkflowId());
            intentionEvent.put("org_id", ctx.getOrgId());
            intentionEvent.put("timestamp", Instant.now().toString());
            intentionEvent.put("event_type", "step_intention");
            intentionEvent.put("step_id", stepId);
            intentionEvent.put("step_name", stepName);
            intentionEvent.put("attempt_id", attemptId);
            engine.getJournal().append(intentionEvent);

            // Execute with timeout
            Instant startTime = Instant.now();
            T result;

            try {
                if (config.getTimeout() != null) {
                    result = executeWithTimeout(fn, config.getTimeout(), ctx.getWorkflowId(), stepId, stepName);
                } else {
                    result = fn.call();
                }
            } catch (StepTimeoutException e) {
                throw e;
            } catch (Exception e) {
                long durationMs = Duration.between(startTime, Instant.now()).toMillis();

                // Log failure
                Map<String, Object> failedEvent = new HashMap<>();
                failedEvent.put("event_id", UUID.randomUUID().toString());
                failedEvent.put("workflow_id", ctx.getWorkflowId());
                failedEvent.put("org_id", ctx.getOrgId());
                failedEvent.put("timestamp", Instant.now().toString());
                failedEvent.put("event_type", "step_failed");
                failedEvent.put("step_id", stepId);
                failedEvent.put("attempt_id", attemptId);
                failedEvent.put("error", e.getMessage());
                engine.getJournal().append(failedEvent);

                // Check retry policy
                if (config.getRetry() != null && config.getRetry().shouldRetry(attemptId, e)) {
                    Duration backoff = config.getRetry().backoff(attemptId);
                    System.out.println("Retrying step " + stepId + ", attempt " + (attemptId + 1) + " after " + backoff);
                    Thread.sleep(backoff.toMillis());
                    return run(stepName, fn);
                }

                // Check max attempts
                if (config.getRetry() != null && attemptId >= config.getRetry().getMaxAttempts()) {
                    throw new TooManyAttemptsException(ctx.getWorkflowId(), stepId, stepName,
                            config.getRetry().getMaxAttempts(), e.getMessage());
                }

                throw new StepExecutionFailedException(ctx.getWorkflowId(), stepId, stepName, attemptId, e);
            }

            long durationMs = Duration.between(startTime, Instant.now()).toMillis();

            // Extract new state
            WorkflowState newState = ctx.extractState(result);
            WorkflowState oldState = ctx.getState();

            // Compute delta
            Map<String, Object> delta = computeDelta(oldState, newState);

            // Write completion
            Map<String, Object> completedEvent = new HashMap<>();
            completedEvent.put("event_id", UUID.randomUUID().toString());
            completedEvent.put("workflow_id", ctx.getWorkflowId());
            completedEvent.put("org_id", ctx.getOrgId());
            completedEvent.put("timestamp", Instant.now().toString());
            completedEvent.put("event_type", "step_completed");
            completedEvent.put("step_id", stepId);
            completedEvent.put("attempt_id", attemptId);
            completedEvent.put("state_delta", delta);
            completedEvent.put("duration_ms", durationMs);
            engine.getJournal().append(completedEvent);

            // Mark completed
            engine.getIdempotency().markCompleted(ctx.getWorkflowId(), stepId, attemptId, newState);

            // Update context
            ctx.setState(newState);
            ctx.incrementStep();

            // Checkpoint if configured
            if (config.isCheckpoint()) {
                engine.maybeSnapshot(newState);
            }

            // Savepoint if configured
            if (config.isSavepoint()) {
                ctx.createSavepoint(null);
            }

            return result;
        }

        private <T> T executeWithTimeout(Callable<T> fn, Duration timeout, String workflowId,
                                         String stepId, String stepName) throws Exception {
            ExecutorService executor = Executors.newSingleThreadExecutor();
            Future<T> future = executor.submit(fn);

            try {
                return future.get(timeout.toMillis(), TimeUnit.MILLISECONDS);
            } catch (TimeoutException e) {
                future.cancel(true);
                throw new StepTimeoutException(workflowId, stepId, stepName,
                        timeout.toSeconds(), timeout.toSeconds());
            } finally {
                executor.shutdownNow();
            }
        }

        private Map<String, Object> computeDelta(WorkflowState oldState, WorkflowState newState) {
            Map<String, Object> delta = new HashMap<>();

            // Find changed/added keys
            for (Map.Entry<String, Object> entry : newState.getVariables().entrySet()) {
                Object oldValue = oldState.getVariables().get(entry.getKey());
                if (oldValue == null || !oldValue.equals(entry.getValue())) {
                    delta.put(entry.getKey(), entry.getValue());
                }
            }

            // Find removed keys
            for (String key : oldState.getVariables().keySet()) {
                if (!newState.getVariables().containsKey(key)) {
                    delta.put(key, null);
                }
            }

            return delta;
        }
    }
}

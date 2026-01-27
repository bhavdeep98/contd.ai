package ai.contd.sdk.testing;

import ai.contd.sdk.ExecutionContext;
import ai.contd.sdk.WorkflowRunner;
import ai.contd.sdk.errors.WorkflowInterruptedException;
import ai.contd.sdk.types.WorkflowConfig;
import ai.contd.sdk.types.WorkflowState;

import java.time.Instant;
import java.util.*;
import java.util.function.Function;

/**
 * Test harness for workflow testing
 */
public class ContdTestCase {
    private final MockEngine engine;
    private final List<WorkflowExecution> executions = new ArrayList<>();
    private WorkflowExecution currentExecution;

    public ContdTestCase() {
        this.engine = new MockEngine();
    }

    /**
     * Set up test fixtures
     */
    public void setUp() {
        engine.reset();
        executions.clear();
        currentExecution = null;
    }

    /**
     * Tear down test fixtures
     */
    public void tearDown() {
        engine.reset();
        ExecutionContext.clear();
    }

    /**
     * Get the mock engine
     */
    public MockEngine getEngine() {
        return engine;
    }

    /**
     * Run a workflow with optional interruption or failure injection
     */
    public <T> T runWorkflow(String workflowName, Function<Object, T> fn, RunWorkflowOptions options) {
        if (options == null) {
            options = new RunWorkflowOptions();
        }

        // Configure mock engine
        if (options.getInterruptAtStep() != null) {
            engine.setInterruptAt(options.getInterruptAtStep());
        }
        if (options.getFailAtStep() != null) {
            engine.setFailAt(options.getFailAtStep(), options.getFailWith());
        }

        // Create execution record
        WorkflowExecution execution = new WorkflowExecution();
        execution.setWorkflowId("wf-" + UUID.randomUUID());
        execution.setWorkflowName(workflowName);
        execution.setStartedAt(Instant.now());
        execution.setStatus("running");
        currentExecution = execution;
        executions.add(execution);

        // Run workflow
        WorkflowRunner runner = new WorkflowRunner(engine, WorkflowConfig.builder().build());

        try {
            T result = runner.run(workflowName, fn, options.getInput());
            execution.setStatus("completed");
            execution.setCompletedAt(Instant.now());
            return result;
        } catch (WorkflowInterruptedException e) {
            execution.setStatus("interrupted");
            execution.setInterruptedAtStep(e.getStepNumber());
            return null;
        } catch (Exception e) {
            execution.setStatus("failed");
            execution.setError(e.getMessage());
            execution.setCompletedAt(Instant.now());
            throw e;
        }
    }

    /**
     * Resume an interrupted workflow
     */
    public <T> T resumeWorkflow(String workflowName, Function<Object, T> fn, Object input) {
        engine.reset();
        return runWorkflow(workflowName, fn, new RunWorkflowOptions().input(input));
    }

    // ========================================================================
    // Assertions
    // ========================================================================

    public void assertCompleted() {
        assertCompleted("");
    }

    public void assertCompleted(String message) {
        if (currentExecution == null) {
            throw new AssertionError("No workflow execution to check");
        }
        if (!"completed".equals(currentExecution.getStatus())) {
            throw new AssertionError("Workflow not completed: status=" + currentExecution.getStatus() + ". " + message);
        }
    }

    public void assertInterrupted() {
        assertInterrupted(null, "");
    }

    public void assertInterrupted(Integer atStep) {
        assertInterrupted(atStep, "");
    }

    public void assertInterrupted(Integer atStep, String message) {
        if (currentExecution == null) {
            throw new AssertionError("No workflow execution to check");
        }
        if (!"interrupted".equals(currentExecution.getStatus())) {
            throw new AssertionError("Workflow not interrupted: status=" + currentExecution.getStatus() + ". " + message);
        }
        if (atStep != null && !atStep.equals(currentExecution.getInterruptedAtStep())) {
            throw new AssertionError("Interrupted at wrong step: expected=" + atStep +
                    ", actual=" + currentExecution.getInterruptedAtStep() + ". " + message);
        }
    }

    public void assertFailed() {
        assertFailed(null, "");
    }

    public void assertFailed(String errorContains) {
        assertFailed(errorContains, "");
    }

    public void assertFailed(String errorContains, String message) {
        if (currentExecution == null) {
            throw new AssertionError("No workflow execution to check");
        }
        if (!"failed".equals(currentExecution.getStatus())) {
            throw new AssertionError("Workflow not failed: status=" + currentExecution.getStatus() + ". " + message);
        }
        if (errorContains != null && (currentExecution.getError() == null ||
                !currentExecution.getError().contains(errorContains))) {
            throw new AssertionError("Error message doesn't contain '" + errorContains +
                    "': actual='" + currentExecution.getError() + "'. " + message);
        }
    }

    public void assertEventCount(int expected) {
        assertEventCount(expected, null, "");
    }

    public void assertEventCount(int expected, String eventType) {
        assertEventCount(expected, eventType, "");
    }

    public void assertEventCount(int expected, String eventType, String message) {
        List<Object> events = getEvents(eventType);
        if (events.size() != expected) {
            throw new AssertionError("Event count mismatch: expected=" + expected +
                    ", actual=" + events.size() + ". " + message);
        }
    }

    // ========================================================================
    // Utilities
    // ========================================================================

    public List<Object> getEvents() {
        return getEvents(null);
    }

    @SuppressWarnings("unchecked")
    public List<Object> getEvents(String eventType) {
        List<Object> events = engine.getRecordedEvents();
        if (eventType == null) {
            return events;
        }
        List<Object> filtered = new ArrayList<>();
        for (Object event : events) {
            if (event instanceof Map<?, ?> map) {
                if (eventType.equals(map.get("event_type"))) {
                    filtered.add(event);
                }
            }
        }
        return filtered;
    }

    public WorkflowState getFinalState() {
        return currentExecution != null ? currentExecution.getFinalState() : null;
    }

    public void printExecutionSummary() {
        if (currentExecution == null) {
            System.out.println("No execution to summarize");
            return;
        }

        System.out.println("\n" + "=".repeat(50));
        System.out.println("Workflow: " + currentExecution.getWorkflowName());
        System.out.println("Status: " + currentExecution.getStatus());
        if (currentExecution.getInterruptedAtStep() != null) {
            System.out.println("Interrupted at: step " + currentExecution.getInterruptedAtStep());
        }
        if (currentExecution.getError() != null) {
            System.out.println("Error: " + currentExecution.getError());
        }
        System.out.println("Events recorded: " + engine.getRecordedEvents().size());
        System.out.println("=".repeat(50) + "\n");
    }

    /**
     * Options for running a workflow in tests
     */
    public static class RunWorkflowOptions {
        private Object input;
        private Integer interruptAtStep;
        private Integer failAtStep;
        private Exception failWith;

        public RunWorkflowOptions input(Object input) {
            this.input = input;
            return this;
        }

        public RunWorkflowOptions interruptAtStep(int step) {
            this.interruptAtStep = step;
            return this;
        }

        public RunWorkflowOptions failAtStep(int step) {
            this.failAtStep = step;
            return this;
        }

        public RunWorkflowOptions failWith(Exception error) {
            this.failWith = error;
            return this;
        }

        public Object getInput() { return input; }
        public Integer getInterruptAtStep() { return interruptAtStep; }
        public Integer getFailAtStep() { return failAtStep; }
        public Exception getFailWith() { return failWith; }
    }

    /**
     * Record of a workflow execution during testing
     */
    public static class WorkflowExecution {
        private String workflowId;
        private String workflowName;
        private Instant startedAt;
        private Instant completedAt;
        private String status;
        private WorkflowState finalState;
        private String error;
        private Integer interruptedAtStep;

        // Getters and setters
        public String getWorkflowId() { return workflowId; }
        public void setWorkflowId(String workflowId) { this.workflowId = workflowId; }
        public String getWorkflowName() { return workflowName; }
        public void setWorkflowName(String workflowName) { this.workflowName = workflowName; }
        public Instant getStartedAt() { return startedAt; }
        public void setStartedAt(Instant startedAt) { this.startedAt = startedAt; }
        public Instant getCompletedAt() { return completedAt; }
        public void setCompletedAt(Instant completedAt) { this.completedAt = completedAt; }
        public String getStatus() { return status; }
        public void setStatus(String status) { this.status = status; }
        public WorkflowState getFinalState() { return finalState; }
        public void setFinalState(WorkflowState finalState) { this.finalState = finalState; }
        public String getError() { return error; }
        public void setError(String error) { this.error = error; }
        public Integer getInterruptedAtStep() { return interruptedAtStep; }
        public void setInterruptedAtStep(Integer interruptedAtStep) { this.interruptedAtStep = interruptedAtStep; }
    }
}

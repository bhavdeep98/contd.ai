package ai.contd.sdk.testing;

import ai.contd.sdk.Engine;
import ai.contd.sdk.errors.WorkflowInterruptedException;
import ai.contd.sdk.types.Lease;
import ai.contd.sdk.types.WorkflowState;

import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Mock execution engine for testing
 */
public class MockEngine implements Engine {
    private Integer interruptAtStep;
    private Integer failAtStep;
    private Exception failWith;
    private final List<Object> recordedEvents = Collections.synchronizedList(new ArrayList<>());
    private final AtomicInteger stepCounter = new AtomicInteger(0);
    private final Map<String, WorkflowState> states = new ConcurrentHashMap<>();
    private final Map<String, WorkflowState> completedSteps = new ConcurrentHashMap<>();

    private final MockLeaseManager leaseManager = new MockLeaseManager();
    private final MockJournal journal = new MockJournal();
    private final MockIdempotencyManager idempotencyManager = new MockIdempotencyManager();

    @Override
    public WorkflowState restore(String workflowId) {
        return states.getOrDefault(workflowId, WorkflowState.builder()
                .workflowId(workflowId)
                .stepNumber(0)
                .variables(new HashMap<>())
                .metadata(new HashMap<>())
                .version("1.0")
                .orgId("default")
                .build());
    }

    @Override
    public void completeWorkflow(String workflowId) {
        WorkflowState state = states.get(workflowId);
        if (state != null) {
            state.getMetadata().put("completed_at", Instant.now().toString());
        }
    }

    @Override
    public void maybeSnapshot(WorkflowState state) {
        states.put(state.getWorkflowId(), state);
    }

    @Override
    public LeaseManager getLeaseManager() {
        return leaseManager;
    }

    @Override
    public Journal getJournal() {
        return journal;
    }

    @Override
    public IdempotencyManager getIdempotency() {
        return idempotencyManager;
    }

    /**
     * Configure interruption at specific step
     */
    public void setInterruptAt(int stepNumber) {
        this.interruptAtStep = stepNumber;
    }

    /**
     * Configure failure injection at specific step
     */
    public void setFailAt(int stepNumber, Exception error) {
        this.failAtStep = stepNumber;
        this.failWith = error;
    }

    /**
     * Check if workflow should be interrupted
     */
    public void checkInterrupt(int stepNumber, String workflowId) {
        if (interruptAtStep != null && stepNumber >= interruptAtStep) {
            throw new WorkflowInterruptedException(workflowId, stepNumber);
        }
    }

    /**
     * Check if failure should be injected
     */
    public void checkFailure(int stepNumber) throws Exception {
        if (failAtStep != null && stepNumber == failAtStep) {
            if (failWith != null) {
                throw failWith;
            }
            throw new RuntimeException("Injected failure at step " + stepNumber);
        }
    }

    /**
     * Get recorded events
     */
    public List<Object> getRecordedEvents() {
        return new ArrayList<>(recordedEvents);
    }

    /**
     * Clear recorded events
     */
    public void clearRecordedEvents() {
        recordedEvents.clear();
    }

    /**
     * Reset all mock state
     */
    public void reset() {
        interruptAtStep = null;
        failAtStep = null;
        failWith = null;
        recordedEvents.clear();
        stepCounter.set(0);
        states.clear();
        completedSteps.clear();
    }

    private class MockLeaseManager implements LeaseManager {
        @Override
        public Lease acquire(String workflowId, String ownerId) {
            return new Lease(workflowId, ownerId, Instant.now().plusSeconds(60));
        }

        @Override
        public void release(Lease lease) {}

        @Override
        public void heartbeat(Lease lease) {}

        @Override
        public Duration getHeartbeatInterval() {
            return Duration.ofSeconds(10);
        }
    }

    private class MockJournal implements Journal {
        @Override
        public void append(Object event) {
            recordedEvents.add(event);
        }
    }

    private class MockIdempotencyManager implements IdempotencyManager {
        @Override
        public WorkflowState checkCompleted(String workflowId, String stepId) {
            return completedSteps.get(workflowId + ":" + stepId);
        }

        @Override
        public int allocateAttempt(String workflowId, String stepId, Lease lease) {
            return stepCounter.incrementAndGet();
        }

        @Override
        public void markCompleted(String workflowId, String stepId, int attemptId, WorkflowState state) {
            completedSteps.put(workflowId + ":" + stepId, state);
        }
    }
}

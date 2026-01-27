package ai.contd.sdk;

import ai.contd.sdk.types.Lease;
import ai.contd.sdk.types.WorkflowState;

import java.time.Duration;

/**
 * Interface for workflow execution engine
 */
public interface Engine {
    /**
     * Restore workflow state from persistence
     */
    WorkflowState restore(String workflowId);

    /**
     * Mark workflow as complete
     */
    void completeWorkflow(String workflowId);

    /**
     * Maybe create a snapshot of the state
     */
    void maybeSnapshot(WorkflowState state);

    /**
     * Get the lease manager
     */
    LeaseManager getLeaseManager();

    /**
     * Get the journal
     */
    Journal getJournal();

    /**
     * Get the idempotency manager
     */
    IdempotencyManager getIdempotency();

    /**
     * Lease manager interface
     */
    interface LeaseManager {
        Lease acquire(String workflowId, String ownerId);
        void release(Lease lease);
        void heartbeat(Lease lease);
        Duration getHeartbeatInterval();
    }

    /**
     * Journal interface for event logging
     */
    interface Journal {
        void append(Object event);
    }

    /**
     * Idempotency manager interface
     */
    interface IdempotencyManager {
        WorkflowState checkCompleted(String workflowId, String stepId);
        int allocateAttempt(String workflowId, String stepId, Lease lease);
        void markCompleted(String workflowId, String stepId, int attemptId, WorkflowState state);
    }
}

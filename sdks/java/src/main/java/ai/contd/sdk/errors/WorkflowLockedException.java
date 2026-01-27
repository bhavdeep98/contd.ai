package ai.contd.sdk.errors;

import java.util.HashMap;
import java.util.Map;

/**
 * Workflow is locked by another executor
 */
public class WorkflowLockedException extends ContdException {
    private final String ownerId;
    private final String expiresAt;

    public WorkflowLockedException(String workflowId) {
        this(workflowId, null, null);
    }

    public WorkflowLockedException(String workflowId, String ownerId, String expiresAt) {
        super("Workflow is locked by another executor", workflowId, buildDetails(ownerId, expiresAt));
        this.ownerId = ownerId;
        this.expiresAt = expiresAt;
    }

    private static Map<String, Object> buildDetails(String ownerId, String expiresAt) {
        Map<String, Object> details = new HashMap<>();
        if (ownerId != null) details.put("current_owner", ownerId);
        if (expiresAt != null) details.put("expires_at", expiresAt);
        return details;
    }

    public String getOwnerId() { return ownerId; }
    public String getExpiresAt() { return expiresAt; }
}

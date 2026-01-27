package ai.contd.sdk.types;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

/**
 * Represents a workflow execution lease
 */
public class Lease {
    @JsonProperty("workflow_id")
    private String workflowId;

    @JsonProperty("owner_id")
    private String ownerId;

    @JsonProperty("expires_at")
    private Instant expiresAt;

    public Lease() {}

    public Lease(String workflowId, String ownerId, Instant expiresAt) {
        this.workflowId = workflowId;
        this.ownerId = ownerId;
        this.expiresAt = expiresAt;
    }

    // Getters and setters
    public String getWorkflowId() { return workflowId; }
    public void setWorkflowId(String workflowId) { this.workflowId = workflowId; }
    public String getOwnerId() { return ownerId; }
    public void setOwnerId(String ownerId) { this.ownerId = ownerId; }
    public Instant getExpiresAt() { return expiresAt; }
    public void setExpiresAt(Instant expiresAt) { this.expiresAt = expiresAt; }
}

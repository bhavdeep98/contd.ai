package ai.contd.sdk.types;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

/**
 * Information about a workflow savepoint
 */
public class SavepointInfo {
    @JsonProperty("savepoint_id")
    private String savepointId;

    @JsonProperty("workflow_id")
    private String workflowId;

    @JsonProperty("step_number")
    private int stepNumber;

    @JsonProperty("created_at")
    private Instant createdAt;

    @JsonProperty("metadata")
    private SavepointMetadata metadata = new SavepointMetadata();

    @JsonProperty("snapshot_size_bytes")
    private Long snapshotSizeBytes;

    public SavepointInfo() {}

    // Getters and setters
    public String getSavepointId() { return savepointId; }
    public void setSavepointId(String savepointId) { this.savepointId = savepointId; }
    public String getWorkflowId() { return workflowId; }
    public void setWorkflowId(String workflowId) { this.workflowId = workflowId; }
    public int getStepNumber() { return stepNumber; }
    public void setStepNumber(int stepNumber) { this.stepNumber = stepNumber; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
    public SavepointMetadata getMetadata() { return metadata; }
    public void setMetadata(SavepointMetadata metadata) { this.metadata = metadata; }
    public Long getSnapshotSizeBytes() { return snapshotSizeBytes; }
    public void setSnapshotSizeBytes(Long snapshotSizeBytes) { this.snapshotSizeBytes = snapshotSizeBytes; }
}

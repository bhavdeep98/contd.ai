package ai.contd.sdk.types;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * Response for workflow status queries
 */
public class WorkflowStatusResponse {
    @JsonProperty("workflow_id")
    private String workflowId;

    @JsonProperty("org_id")
    private String orgId;

    @JsonProperty("status")
    private WorkflowStatus status;

    @JsonProperty("current_step")
    private int currentStep;

    @JsonProperty("total_steps")
    private Integer totalSteps;

    @JsonProperty("has_lease")
    private boolean hasLease;

    @JsonProperty("lease_owner")
    private String leaseOwner;

    @JsonProperty("lease_expires_at")
    private Instant leaseExpiresAt;

    @JsonProperty("event_count")
    private int eventCount;

    @JsonProperty("snapshot_count")
    private int snapshotCount;

    @JsonProperty("latest_snapshot_step")
    private Integer latestSnapshotStep;

    @JsonProperty("savepoints")
    private List<SavepointInfo> savepoints = new ArrayList<>();

    public WorkflowStatusResponse() {}

    // Getters and setters
    public String getWorkflowId() { return workflowId; }
    public void setWorkflowId(String workflowId) { this.workflowId = workflowId; }
    public String getOrgId() { return orgId; }
    public void setOrgId(String orgId) { this.orgId = orgId; }
    public WorkflowStatus getStatus() { return status; }
    public void setStatus(WorkflowStatus status) { this.status = status; }
    public int getCurrentStep() { return currentStep; }
    public void setCurrentStep(int currentStep) { this.currentStep = currentStep; }
    public Integer getTotalSteps() { return totalSteps; }
    public void setTotalSteps(Integer totalSteps) { this.totalSteps = totalSteps; }
    public boolean isHasLease() { return hasLease; }
    public void setHasLease(boolean hasLease) { this.hasLease = hasLease; }
    public String getLeaseOwner() { return leaseOwner; }
    public void setLeaseOwner(String leaseOwner) { this.leaseOwner = leaseOwner; }
    public Instant getLeaseExpiresAt() { return leaseExpiresAt; }
    public void setLeaseExpiresAt(Instant leaseExpiresAt) { this.leaseExpiresAt = leaseExpiresAt; }
    public int getEventCount() { return eventCount; }
    public void setEventCount(int eventCount) { this.eventCount = eventCount; }
    public int getSnapshotCount() { return snapshotCount; }
    public void setSnapshotCount(int snapshotCount) { this.snapshotCount = snapshotCount; }
    public Integer getLatestSnapshotStep() { return latestSnapshotStep; }
    public void setLatestSnapshotStep(Integer latestSnapshotStep) { this.latestSnapshotStep = latestSnapshotStep; }
    public List<SavepointInfo> getSavepoints() { return savepoints; }
    public void setSavepoints(List<SavepointInfo> savepoints) { this.savepoints = savepoints; }
}

package ai.contd.sdk.types;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.HashMap;
import java.util.Map;

/**
 * Represents the state of a workflow
 */
public class WorkflowState {
    @JsonProperty("workflow_id")
    private String workflowId;

    @JsonProperty("step_number")
    private int stepNumber;

    @JsonProperty("variables")
    private Map<String, Object> variables = new HashMap<>();

    @JsonProperty("metadata")
    private Map<String, Object> metadata = new HashMap<>();

    @JsonProperty("version")
    private String version = "1.0";

    @JsonProperty("checksum")
    private String checksum = "";

    @JsonProperty("org_id")
    private String orgId;

    public WorkflowState() {}

    public WorkflowState(String workflowId, int stepNumber, Map<String, Object> variables,
                         Map<String, Object> metadata, String version, String checksum, String orgId) {
        this.workflowId = workflowId;
        this.stepNumber = stepNumber;
        this.variables = variables != null ? variables : new HashMap<>();
        this.metadata = metadata != null ? metadata : new HashMap<>();
        this.version = version;
        this.checksum = checksum;
        this.orgId = orgId;
    }

    // Getters and setters
    public String getWorkflowId() { return workflowId; }
    public void setWorkflowId(String workflowId) { this.workflowId = workflowId; }
    public int getStepNumber() { return stepNumber; }
    public void setStepNumber(int stepNumber) { this.stepNumber = stepNumber; }
    public Map<String, Object> getVariables() { return variables; }
    public void setVariables(Map<String, Object> variables) { this.variables = variables; }
    public Map<String, Object> getMetadata() { return metadata; }
    public void setMetadata(Map<String, Object> metadata) { this.metadata = metadata; }
    public String getVersion() { return version; }
    public void setVersion(String version) { this.version = version; }
    public String getChecksum() { return checksum; }
    public void setChecksum(String checksum) { this.checksum = checksum; }
    public String getOrgId() { return orgId; }
    public void setOrgId(String orgId) { this.orgId = orgId; }

    /**
     * Get a variable value
     */
    @SuppressWarnings("unchecked")
    public <T> T getVariable(String key) {
        return (T) variables.get(key);
    }

    /**
     * Set a variable value
     */
    public void setVariable(String key, Object value) {
        variables.put(key, value);
    }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private final WorkflowState state = new WorkflowState();

        public Builder workflowId(String workflowId) {
            state.workflowId = workflowId;
            return this;
        }

        public Builder stepNumber(int stepNumber) {
            state.stepNumber = stepNumber;
            return this;
        }

        public Builder variables(Map<String, Object> variables) {
            state.variables = variables;
            return this;
        }

        public Builder variable(String key, Object value) {
            state.variables.put(key, value);
            return this;
        }

        public Builder metadata(Map<String, Object> metadata) {
            state.metadata = metadata;
            return this;
        }

        public Builder version(String version) {
            state.version = version;
            return this;
        }

        public Builder checksum(String checksum) {
            state.checksum = checksum;
            return this;
        }

        public Builder orgId(String orgId) {
            state.orgId = orgId;
            return this;
        }

        public WorkflowState build() {
            return state;
        }
    }
}

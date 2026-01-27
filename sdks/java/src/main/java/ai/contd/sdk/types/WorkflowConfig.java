package ai.contd.sdk.types;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

/**
 * Configuration for workflow execution
 */
public class WorkflowConfig {
    @JsonProperty("workflow_id")
    private String workflowId;

    @JsonProperty("max_duration")
    private Duration maxDuration;

    @JsonProperty("retry_policy")
    private RetryPolicy retryPolicy;

    @JsonProperty("tags")
    private Map<String, String> tags = new HashMap<>();

    @JsonProperty("org_id")
    private String orgId;

    public WorkflowConfig() {}

    // Getters and setters
    public String getWorkflowId() { return workflowId; }
    public void setWorkflowId(String workflowId) { this.workflowId = workflowId; }
    public Duration getMaxDuration() { return maxDuration; }
    public void setMaxDuration(Duration maxDuration) { this.maxDuration = maxDuration; }
    public RetryPolicy getRetryPolicy() { return retryPolicy; }
    public void setRetryPolicy(RetryPolicy retryPolicy) { this.retryPolicy = retryPolicy; }
    public Map<String, String> getTags() { return tags; }
    public void setTags(Map<String, String> tags) { this.tags = tags; }
    public String getOrgId() { return orgId; }
    public void setOrgId(String orgId) { this.orgId = orgId; }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private final WorkflowConfig config = new WorkflowConfig();

        public Builder workflowId(String workflowId) {
            config.workflowId = workflowId;
            return this;
        }

        public Builder maxDuration(Duration maxDuration) {
            config.maxDuration = maxDuration;
            return this;
        }

        public Builder retryPolicy(RetryPolicy retryPolicy) {
            config.retryPolicy = retryPolicy;
            return this;
        }

        public Builder tags(Map<String, String> tags) {
            config.tags = tags;
            return this;
        }

        public Builder tag(String key, String value) {
            config.tags.put(key, value);
            return this;
        }

        public Builder orgId(String orgId) {
            config.orgId = orgId;
            return this;
        }

        public WorkflowConfig build() {
            return config;
        }
    }
}

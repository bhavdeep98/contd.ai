package ai.contd.sdk.types;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Duration;

/**
 * Configuration for step execution
 */
public class StepConfig {
    @JsonProperty("checkpoint")
    private boolean checkpoint = true;

    @JsonProperty("idempotency_key")
    private String idempotencyKey;

    @JsonProperty("retry")
    private RetryPolicy retry;

    @JsonProperty("timeout")
    private Duration timeout;

    @JsonProperty("savepoint")
    private boolean savepoint = false;

    public StepConfig() {}

    // Getters and setters
    public boolean isCheckpoint() { return checkpoint; }
    public void setCheckpoint(boolean checkpoint) { this.checkpoint = checkpoint; }
    public String getIdempotencyKey() { return idempotencyKey; }
    public void setIdempotencyKey(String idempotencyKey) { this.idempotencyKey = idempotencyKey; }
    public RetryPolicy getRetry() { return retry; }
    public void setRetry(RetryPolicy retry) { this.retry = retry; }
    public Duration getTimeout() { return timeout; }
    public void setTimeout(Duration timeout) { this.timeout = timeout; }
    public boolean isSavepoint() { return savepoint; }
    public void setSavepoint(boolean savepoint) { this.savepoint = savepoint; }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private final StepConfig config = new StepConfig();

        public Builder checkpoint(boolean checkpoint) {
            config.checkpoint = checkpoint;
            return this;
        }

        public Builder idempotencyKey(String idempotencyKey) {
            config.idempotencyKey = idempotencyKey;
            return this;
        }

        public Builder retry(RetryPolicy retry) {
            config.retry = retry;
            return this;
        }

        public Builder timeout(Duration timeout) {
            config.timeout = timeout;
            return this;
        }

        public Builder savepoint(boolean savepoint) {
            config.savepoint = savepoint;
            return this;
        }

        public StepConfig build() {
            return config;
        }
    }
}

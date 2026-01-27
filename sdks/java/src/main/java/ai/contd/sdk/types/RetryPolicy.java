package ai.contd.sdk.types;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Duration;
import java.util.Random;

/**
 * Configurable retry policy with exponential backoff
 */
public class RetryPolicy {
    private static final Random RANDOM = new Random();

    @JsonProperty("max_attempts")
    private int maxAttempts = 3;

    @JsonProperty("backoff_base")
    private double backoffBase = 2.0;

    @JsonProperty("backoff_max")
    private double backoffMax = 60.0;

    @JsonProperty("backoff_jitter")
    private double backoffJitter = 0.5;

    public RetryPolicy() {}

    public RetryPolicy(int maxAttempts, double backoffBase, double backoffMax, double backoffJitter) {
        this.maxAttempts = maxAttempts;
        this.backoffBase = backoffBase;
        this.backoffMax = backoffMax;
        this.backoffJitter = backoffJitter;
    }

    /**
     * Check if retry should be attempted
     */
    public boolean shouldRetry(int attempt, Exception error) {
        return attempt < maxAttempts;
    }

    /**
     * Calculate backoff duration with exponential growth and jitter
     */
    public Duration backoff(int attempt) {
        double delay = Math.min(Math.pow(backoffBase, attempt), backoffMax);
        double jitterRange = delay * backoffJitter;
        delay = delay - jitterRange / 2 + RANDOM.nextDouble() * jitterRange;
        return Duration.ofMillis((long) (delay * 1000));
    }

    // Getters and setters
    public int getMaxAttempts() { return maxAttempts; }
    public void setMaxAttempts(int maxAttempts) { this.maxAttempts = maxAttempts; }
    public double getBackoffBase() { return backoffBase; }
    public void setBackoffBase(double backoffBase) { this.backoffBase = backoffBase; }
    public double getBackoffMax() { return backoffMax; }
    public void setBackoffMax(double backoffMax) { this.backoffMax = backoffMax; }
    public double getBackoffJitter() { return backoffJitter; }
    public void setBackoffJitter(double backoffJitter) { this.backoffJitter = backoffJitter; }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private int maxAttempts = 3;
        private double backoffBase = 2.0;
        private double backoffMax = 60.0;
        private double backoffJitter = 0.5;

        public Builder maxAttempts(int maxAttempts) {
            this.maxAttempts = maxAttempts;
            return this;
        }

        public Builder backoffBase(double backoffBase) {
            this.backoffBase = backoffBase;
            return this;
        }

        public Builder backoffMax(double backoffMax) {
            this.backoffMax = backoffMax;
            return this;
        }

        public Builder backoffJitter(double backoffJitter) {
            this.backoffJitter = backoffJitter;
            return this;
        }

        public RetryPolicy build() {
            return new RetryPolicy(maxAttempts, backoffBase, backoffMax, backoffJitter);
        }
    }
}

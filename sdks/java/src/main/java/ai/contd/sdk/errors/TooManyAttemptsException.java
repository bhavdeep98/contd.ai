package ai.contd.sdk.errors;

/**
 * Step exceeded maximum retry attempts
 */
public class TooManyAttemptsException extends StepException {
    private final int maxAttempts;
    private final String lastError;

    public TooManyAttemptsException(String workflowId, String stepId, String stepName,
                                    int maxAttempts, String lastError) {
        super(String.format("Step exceeded %d retry attempts", maxAttempts),
              workflowId, stepId, stepName, null);
        this.maxAttempts = maxAttempts;
        this.lastError = lastError;
    }

    public int getMaxAttempts() { return maxAttempts; }
    public String getLastError() { return lastError; }
}

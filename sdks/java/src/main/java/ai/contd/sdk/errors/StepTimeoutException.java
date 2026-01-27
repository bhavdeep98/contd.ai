package ai.contd.sdk.errors;

/**
 * Step exceeded configured timeout
 */
public class StepTimeoutException extends StepException {
    private final double timeoutSeconds;
    private final double elapsedSeconds;

    public StepTimeoutException(String workflowId, String stepId, String stepName,
                                double timeoutSeconds, double elapsedSeconds) {
        super(String.format("Step timed out after %.2fs (limit: %.0fs)", elapsedSeconds, timeoutSeconds),
              workflowId, stepId, stepName, null);
        this.timeoutSeconds = timeoutSeconds;
        this.elapsedSeconds = elapsedSeconds;
    }

    public double getTimeoutSeconds() { return timeoutSeconds; }
    public double getElapsedSeconds() { return elapsedSeconds; }
}

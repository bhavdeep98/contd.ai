package ai.contd.sdk.errors;

/**
 * Step execution failed with an unrecoverable error
 */
public class StepExecutionFailedException extends StepException {
    private final Throwable originalError;

    public StepExecutionFailedException(String workflowId, String stepId, String stepName,
                                        int attempt, Throwable originalError) {
        super("Step execution failed: " + originalError.getMessage(),
              workflowId, stepId, stepName, attempt);
        this.originalError = originalError;
    }

    public Throwable getOriginalError() { return originalError; }

    @Override
    public synchronized Throwable getCause() {
        return originalError;
    }
}

package ai.contd.sdk.errors;

/**
 * No workflow context found in current execution
 */
public class NoActiveWorkflowException extends ContdException {
    public NoActiveWorkflowException() {
        this("No active workflow context");
    }

    public NoActiveWorkflowException(String message) {
        super(message);
    }
}

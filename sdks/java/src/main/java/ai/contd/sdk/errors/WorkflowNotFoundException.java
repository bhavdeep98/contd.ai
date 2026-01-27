package ai.contd.sdk.errors;

/**
 * Workflow does not exist in persistence
 */
public class WorkflowNotFoundException extends ContdException {
    public WorkflowNotFoundException(String workflowId) {
        super("Workflow not found", workflowId);
    }
}

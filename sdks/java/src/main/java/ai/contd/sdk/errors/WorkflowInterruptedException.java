package ai.contd.sdk.errors;

import java.util.Map;

/**
 * Workflow was intentionally interrupted (for testing)
 */
public class WorkflowInterruptedException extends ContdException {
    private final int stepNumber;

    public WorkflowInterruptedException(String workflowId, int stepNumber) {
        super(String.format("Workflow interrupted at step %d for testing", stepNumber),
              workflowId, Map.of("interrupted_at_step", stepNumber));
        this.stepNumber = stepNumber;
    }

    public int getStepNumber() { return stepNumber; }
}

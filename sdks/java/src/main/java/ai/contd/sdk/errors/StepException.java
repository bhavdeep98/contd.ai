package ai.contd.sdk.errors;

import java.util.HashMap;
import java.util.Map;

/**
 * Base exception for step-related errors
 */
public class StepException extends ContdException {
    private final String stepId;
    private final String stepName;
    private final Integer attempt;

    public StepException(String message, String workflowId, String stepId, String stepName, Integer attempt) {
        super(message, workflowId, buildDetails(stepId, stepName, attempt));
        this.stepId = stepId;
        this.stepName = stepName;
        this.attempt = attempt;
    }

    private static Map<String, Object> buildDetails(String stepId, String stepName, Integer attempt) {
        Map<String, Object> details = new HashMap<>();
        if (stepId != null) details.put("step_id", stepId);
        if (stepName != null) details.put("step_name", stepName);
        if (attempt != null) details.put("attempt", attempt);
        return details;
    }

    public String getStepId() { return stepId; }
    public String getStepName() { return stepName; }
    public Integer getAttempt() { return attempt; }
}

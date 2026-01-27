package ai.contd.sdk.errors;

import java.util.HashMap;
import java.util.Map;

/**
 * Base exception for all Contd SDK errors
 */
public class ContdException extends RuntimeException {
    private final String workflowId;
    private final Map<String, Object> details;

    public ContdException(String message) {
        this(message, null, null);
    }

    public ContdException(String message, String workflowId) {
        this(message, workflowId, null);
    }

    public ContdException(String message, String workflowId, Map<String, Object> details) {
        super(formatMessage(message, workflowId, details));
        this.workflowId = workflowId;
        this.details = details != null ? details : new HashMap<>();
    }

    public ContdException(String message, Throwable cause) {
        super(message, cause);
        this.workflowId = null;
        this.details = new HashMap<>();
    }

    private static String formatMessage(String message, String workflowId, Map<String, Object> details) {
        StringBuilder sb = new StringBuilder(message);
        if (workflowId != null) {
            sb.append(" [workflow=").append(workflowId).append("]");
        }
        if (details != null && !details.isEmpty()) {
            sb.append(" details=").append(details);
        }
        return sb.toString();
    }

    public String getWorkflowId() {
        return workflowId;
    }

    public Map<String, Object> getDetails() {
        return details;
    }
}

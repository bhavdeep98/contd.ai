package ai.contd.sdk.types;

import com.fasterxml.jackson.annotation.JsonValue;

/**
 * Workflow execution status
 */
public enum WorkflowStatus {
    PENDING("pending"),
    RUNNING("running"),
    SUSPENDED("suspended"),
    COMPLETED("completed"),
    FAILED("failed"),
    CANCELLED("cancelled");

    private final String value;

    WorkflowStatus(String value) {
        this.value = value;
    }

    @JsonValue
    public String getValue() {
        return value;
    }

    public static WorkflowStatus fromValue(String value) {
        for (WorkflowStatus status : values()) {
            if (status.value.equals(value)) {
                return status;
            }
        }
        throw new IllegalArgumentException("Unknown workflow status: " + value);
    }
}

package ai.contd.sdk.types;

import com.fasterxml.jackson.annotation.JsonValue;

/**
 * Step execution status
 */
public enum StepStatus {
    PENDING("pending"),
    RUNNING("running"),
    COMPLETED("completed"),
    FAILED("failed"),
    SKIPPED("skipped");

    private final String value;

    StepStatus(String value) {
        this.value = value;
    }

    @JsonValue
    public String getValue() {
        return value;
    }

    public static StepStatus fromValue(String value) {
        for (StepStatus status : values()) {
            if (status.value.equals(value)) {
                return status;
            }
        }
        throw new IllegalArgumentException("Unknown step status: " + value);
    }
}

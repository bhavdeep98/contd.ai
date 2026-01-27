package contd

import (
	"fmt"
)

// ContdError is the base error type for all Contd SDK errors
type ContdError struct {
	Message    string
	WorkflowID string
	Details    map[string]interface{}
}

func (e *ContdError) Error() string {
	msg := e.Message
	if e.WorkflowID != "" {
		msg += fmt.Sprintf(" [workflow=%s]", e.WorkflowID)
	}
	if len(e.Details) > 0 {
		msg += fmt.Sprintf(" details=%v", e.Details)
	}
	return msg
}

// NewContdError creates a new ContdError
func NewContdError(message string, workflowID string, details map[string]interface{}) *ContdError {
	return &ContdError{
		Message:    message,
		WorkflowID: workflowID,
		Details:    details,
	}
}

// WorkflowLocked indicates the workflow is locked by another executor
type WorkflowLocked struct {
	ContdError
	OwnerID   string
	ExpiresAt string
}

// NewWorkflowLocked creates a new WorkflowLocked error
func NewWorkflowLocked(workflowID, ownerID, expiresAt string) *WorkflowLocked {
	details := make(map[string]interface{})
	if ownerID != "" {
		details["current_owner"] = ownerID
	}
	if expiresAt != "" {
		details["expires_at"] = expiresAt
	}
	return &WorkflowLocked{
		ContdError: ContdError{
			Message:    "Workflow is locked by another executor",
			WorkflowID: workflowID,
			Details:    details,
		},
		OwnerID:   ownerID,
		ExpiresAt: expiresAt,
	}
}

// NoActiveWorkflow indicates no workflow context is active
type NoActiveWorkflow struct {
	ContdError
}

// NewNoActiveWorkflow creates a new NoActiveWorkflow error
func NewNoActiveWorkflow(message string) *NoActiveWorkflow {
	if message == "" {
		message = "No active workflow context"
	}
	return &NoActiveWorkflow{
		ContdError: ContdError{Message: message},
	}
}

// WorkflowNotFound indicates the workflow does not exist
type WorkflowNotFound struct {
	ContdError
}

// NewWorkflowNotFound creates a new WorkflowNotFound error
func NewWorkflowNotFound(workflowID string) *WorkflowNotFound {
	return &WorkflowNotFound{
		ContdError: ContdError{
			Message:    "Workflow not found",
			WorkflowID: workflowID,
		},
	}
}

// WorkflowAlreadyCompleted indicates the workflow has already completed
type WorkflowAlreadyCompleted struct {
	ContdError
	CompletedAt string
}

// NewWorkflowAlreadyCompleted creates a new WorkflowAlreadyCompleted error
func NewWorkflowAlreadyCompleted(workflowID, completedAt string) *WorkflowAlreadyCompleted {
	details := make(map[string]interface{})
	if completedAt != "" {
		details["completed_at"] = completedAt
	}
	return &WorkflowAlreadyCompleted{
		ContdError: ContdError{
			Message:    "Workflow has already completed",
			WorkflowID: workflowID,
			Details:    details,
		},
		CompletedAt: completedAt,
	}
}

// StepError is the base error for step-related errors
type StepError struct {
	ContdError
	StepID   string
	StepName string
	Attempt  int
}

// NewStepError creates a new StepError
func NewStepError(message, workflowID, stepID, stepName string, attempt int, details map[string]interface{}) *StepError {
	if details == nil {
		details = make(map[string]interface{})
	}
	if stepID != "" {
		details["step_id"] = stepID
	}
	if stepName != "" {
		details["step_name"] = stepName
	}
	if attempt > 0 {
		details["attempt"] = attempt
	}
	return &StepError{
		ContdError: ContdError{
			Message:    message,
			WorkflowID: workflowID,
			Details:    details,
		},
		StepID:   stepID,
		StepName: stepName,
		Attempt:  attempt,
	}
}

// StepTimeout indicates a step exceeded its timeout
type StepTimeout struct {
	StepError
	TimeoutSeconds float64
	ElapsedSeconds float64
}

// NewStepTimeout creates a new StepTimeout error
func NewStepTimeout(workflowID, stepID, stepName string, timeoutSeconds, elapsedSeconds float64) *StepTimeout {
	return &StepTimeout{
		StepError: StepError{
			ContdError: ContdError{
				Message:    fmt.Sprintf("Step timed out after %.2fs (limit: %.0fs)", elapsedSeconds, timeoutSeconds),
				WorkflowID: workflowID,
				Details: map[string]interface{}{
					"step_id":         stepID,
					"step_name":       stepName,
					"timeout_seconds": timeoutSeconds,
					"elapsed_seconds": elapsedSeconds,
				},
			},
			StepID:   stepID,
			StepName: stepName,
		},
		TimeoutSeconds: timeoutSeconds,
		ElapsedSeconds: elapsedSeconds,
	}
}

// TooManyAttempts indicates a step exceeded maximum retry attempts
type TooManyAttempts struct {
	StepError
	MaxAttempts int
	LastError   string
}

// NewTooManyAttempts creates a new TooManyAttempts error
func NewTooManyAttempts(workflowID, stepID, stepName string, maxAttempts int, lastError string) *TooManyAttempts {
	details := map[string]interface{}{
		"step_id":      stepID,
		"step_name":    stepName,
		"max_attempts": maxAttempts,
	}
	if lastError != "" {
		details["last_error"] = lastError
	}
	return &TooManyAttempts{
		StepError: StepError{
			ContdError: ContdError{
				Message:    fmt.Sprintf("Step exceeded %d retry attempts", maxAttempts),
				WorkflowID: workflowID,
				Details:    details,
			},
			StepID:   stepID,
			StepName: stepName,
		},
		MaxAttempts: maxAttempts,
		LastError:   lastError,
	}
}

// StepExecutionFailed indicates a step execution failed
type StepExecutionFailed struct {
	StepError
	OriginalError error
}

// NewStepExecutionFailed creates a new StepExecutionFailed error
func NewStepExecutionFailed(workflowID, stepID, stepName string, attempt int, originalError error) *StepExecutionFailed {
	return &StepExecutionFailed{
		StepError: StepError{
			ContdError: ContdError{
				Message:    fmt.Sprintf("Step execution failed: %v", originalError),
				WorkflowID: workflowID,
				Details: map[string]interface{}{
					"step_id":             stepID,
					"step_name":           stepName,
					"attempt":             attempt,
					"original_error_type": fmt.Sprintf("%T", originalError),
				},
			},
			StepID:   stepID,
			StepName: stepName,
			Attempt:  attempt,
		},
		OriginalError: originalError,
	}
}

// Unwrap returns the original error
func (e *StepExecutionFailed) Unwrap() error {
	return e.OriginalError
}

// IntegrityError is the base error for data integrity errors
type IntegrityError struct {
	ContdError
}

// ChecksumMismatch indicates a checksum validation failed
type ChecksumMismatch struct {
	IntegrityError
	ResourceType string
	Expected     string
	Actual       string
}

// NewChecksumMismatch creates a new ChecksumMismatch error
func NewChecksumMismatch(workflowID, resourceType, expected, actual string) *ChecksumMismatch {
	return &ChecksumMismatch{
		IntegrityError: IntegrityError{
			ContdError: ContdError{
				Message:    fmt.Sprintf("%s checksum mismatch", resourceType),
				WorkflowID: workflowID,
				Details: map[string]interface{}{
					"resource_type":     resourceType,
					"expected_checksum": expected[:16] + "...",
					"actual_checksum":   actual[:16] + "...",
				},
			},
		},
		ResourceType: resourceType,
		Expected:     expected,
		Actual:       actual,
	}
}

// PersistenceError is the base error for persistence layer errors
type PersistenceError struct {
	ContdError
}

// NewPersistenceError creates a new PersistenceError
func NewPersistenceError(message, workflowID string, details map[string]interface{}) *PersistenceError {
	return &PersistenceError{
		ContdError: ContdError{
			Message:    message,
			WorkflowID: workflowID,
			Details:    details,
		},
	}
}

// RecoveryError is the base error for recovery-related errors
type RecoveryError struct {
	ContdError
}

// RecoveryFailed indicates workflow recovery failed
type RecoveryFailed struct {
	RecoveryError
	Recoverable bool
}

// NewRecoveryFailed creates a new RecoveryFailed error
func NewRecoveryFailed(workflowID, reason string, recoverable bool) *RecoveryFailed {
	return &RecoveryFailed{
		RecoveryError: RecoveryError{
			ContdError: ContdError{
				Message:    fmt.Sprintf("Recovery failed: %s", reason),
				WorkflowID: workflowID,
				Details:    map[string]interface{}{"recoverable": recoverable},
			},
		},
		Recoverable: recoverable,
	}
}

// InvalidSavepoint indicates a savepoint is invalid
type InvalidSavepoint struct {
	RecoveryError
	SavepointID string
}

// NewInvalidSavepoint creates a new InvalidSavepoint error
func NewInvalidSavepoint(workflowID, savepointID, reason string) *InvalidSavepoint {
	return &InvalidSavepoint{
		RecoveryError: RecoveryError{
			ContdError: ContdError{
				Message:    fmt.Sprintf("Invalid savepoint: %s", reason),
				WorkflowID: workflowID,
				Details:    map[string]interface{}{"savepoint_id": savepointID},
			},
		},
		SavepointID: savepointID,
	}
}

// ConfigurationError indicates invalid SDK configuration
type ConfigurationError struct {
	ContdError
	ConfigKey string
}

// NewConfigurationError creates a new ConfigurationError
func NewConfigurationError(message, configKey string) *ConfigurationError {
	details := make(map[string]interface{})
	if configKey != "" {
		details["config_key"] = configKey
	}
	return &ConfigurationError{
		ContdError: ContdError{
			Message: message,
			Details: details,
		},
		ConfigKey: configKey,
	}
}

// WorkflowInterrupted indicates a workflow was intentionally interrupted (for testing)
type WorkflowInterrupted struct {
	ContdError
	StepNumber int
}

// NewWorkflowInterrupted creates a new WorkflowInterrupted error
func NewWorkflowInterrupted(workflowID string, stepNumber int) *WorkflowInterrupted {
	return &WorkflowInterrupted{
		ContdError: ContdError{
			Message:    fmt.Sprintf("Workflow interrupted at step %d for testing", stepNumber),
			WorkflowID: workflowID,
			Details:    map[string]interface{}{"interrupted_at_step": stepNumber},
		},
		StepNumber: stepNumber,
	}
}

// Package contd provides the Contd SDK for Go
// Resumable workflows with exactly-once execution semantics
package contd

import (
	"time"
)

// WorkflowStatus represents the status of a workflow
type WorkflowStatus string

const (
	WorkflowStatusPending   WorkflowStatus = "pending"
	WorkflowStatusRunning   WorkflowStatus = "running"
	WorkflowStatusSuspended WorkflowStatus = "suspended"
	WorkflowStatusCompleted WorkflowStatus = "completed"
	WorkflowStatusFailed    WorkflowStatus = "failed"
	WorkflowStatusCancelled WorkflowStatus = "cancelled"
)

// StepStatus represents the status of a step
type StepStatus string

const (
	StepStatusPending   StepStatus = "pending"
	StepStatusRunning   StepStatus = "running"
	StepStatusCompleted StepStatus = "completed"
	StepStatusFailed    StepStatus = "failed"
	StepStatusSkipped   StepStatus = "skipped"
)

// RetryPolicy configures retry behavior for steps
type RetryPolicy struct {
	MaxAttempts   int           `json:"max_attempts"`
	BackoffBase   float64       `json:"backoff_base"`
	BackoffMax    float64       `json:"backoff_max"`
	BackoffJitter float64       `json:"backoff_jitter"`
}

// DefaultRetryPolicy returns a sensible default retry policy
func DefaultRetryPolicy() RetryPolicy {
	return RetryPolicy{
		MaxAttempts:   3,
		BackoffBase:   2.0,
		BackoffMax:    60.0,
		BackoffJitter: 0.5,
	}
}

// ShouldRetry determines if a retry should be attempted
func (p RetryPolicy) ShouldRetry(attempt int, err error) bool {
	return attempt < p.MaxAttempts
}

// Backoff calculates the backoff duration for an attempt
func (p RetryPolicy) Backoff(attempt int) time.Duration {
	delay := p.BackoffBase
	for i := 1; i < attempt; i++ {
		delay *= p.BackoffBase
	}
	if delay > p.BackoffMax {
		delay = p.BackoffMax
	}
	// Add jitter
	jitterRange := delay * p.BackoffJitter
	delay = delay - jitterRange/2 + jitterRange*0.5 // Simplified jitter
	return time.Duration(delay * float64(time.Second))
}

// WorkflowConfig configures workflow execution
type WorkflowConfig struct {
	WorkflowID  string            `json:"workflow_id,omitempty"`
	MaxDuration time.Duration     `json:"max_duration,omitempty"`
	RetryPolicy *RetryPolicy      `json:"retry_policy,omitempty"`
	Tags        map[string]string `json:"tags,omitempty"`
	OrgID       string            `json:"org_id,omitempty"`
}

// StepConfig configures step execution
type StepConfig struct {
	Checkpoint     bool          `json:"checkpoint"`
	IdempotencyKey string        `json:"idempotency_key,omitempty"`
	Retry          *RetryPolicy  `json:"retry,omitempty"`
	Timeout        time.Duration `json:"timeout,omitempty"`
	Savepoint      bool          `json:"savepoint"`
}

// DefaultStepConfig returns a sensible default step config
func DefaultStepConfig() StepConfig {
	return StepConfig{
		Checkpoint: true,
		Savepoint:  false,
	}
}

// WorkflowState represents the state of a workflow
type WorkflowState struct {
	WorkflowID string                 `json:"workflow_id"`
	StepNumber int                    `json:"step_number"`
	Variables  map[string]interface{} `json:"variables"`
	Metadata   map[string]interface{} `json:"metadata"`
	Version    string                 `json:"version"`
	Checksum   string                 `json:"checksum"`
	OrgID      string                 `json:"org_id"`
}

// SavepointMetadata contains rich metadata for savepoints
type SavepointMetadata struct {
	GoalSummary string                   `json:"goal_summary"`
	Hypotheses  []string                 `json:"hypotheses"`
	Questions   []string                 `json:"questions"`
	Decisions   []map[string]interface{} `json:"decisions"`
	NextStep    string                   `json:"next_step"`
}

// SavepointInfo contains information about a savepoint
type SavepointInfo struct {
	SavepointID       string            `json:"savepoint_id"`
	WorkflowID        string            `json:"workflow_id"`
	StepNumber        int               `json:"step_number"`
	CreatedAt         time.Time         `json:"created_at"`
	Metadata          SavepointMetadata `json:"metadata"`
	SnapshotSizeBytes int64             `json:"snapshot_size_bytes,omitempty"`
}

// WorkflowResult represents the result of a workflow execution
type WorkflowResult struct {
	WorkflowID  string                 `json:"workflow_id"`
	Status      WorkflowStatus         `json:"status"`
	Result      map[string]interface{} `json:"result,omitempty"`
	Error       string                 `json:"error,omitempty"`
	StartedAt   time.Time              `json:"started_at"`
	CompletedAt *time.Time             `json:"completed_at,omitempty"`
	DurationMs  int64                  `json:"duration_ms,omitempty"`
	StepCount   int                    `json:"step_count"`
}

// StepResult represents the result of a step execution
type StepResult struct {
	StepID     string      `json:"step_id"`
	StepName   string      `json:"step_name"`
	Status     StepStatus  `json:"status"`
	Attempt    int         `json:"attempt"`
	Result     interface{} `json:"result,omitempty"`
	Error      string      `json:"error,omitempty"`
	DurationMs int64       `json:"duration_ms"`
	WasCached  bool        `json:"was_cached"`
}

// WorkflowStatusResponse represents the response for workflow status queries
type WorkflowStatusResponse struct {
	WorkflowID         string          `json:"workflow_id"`
	OrgID              string          `json:"org_id"`
	Status             WorkflowStatus  `json:"status"`
	CurrentStep        int             `json:"current_step"`
	TotalSteps         *int            `json:"total_steps,omitempty"`
	HasLease           bool            `json:"has_lease"`
	LeaseOwner         string          `json:"lease_owner,omitempty"`
	LeaseExpiresAt     *time.Time      `json:"lease_expires_at,omitempty"`
	EventCount         int             `json:"event_count"`
	SnapshotCount      int             `json:"snapshot_count"`
	LatestSnapshotStep *int            `json:"latest_snapshot_step,omitempty"`
	Savepoints         []SavepointInfo `json:"savepoints"`
}

// HealthCheck represents a health check response
type HealthCheck struct {
	Status     string            `json:"status"`
	Version    string            `json:"version"`
	Components map[string]string `json:"components"`
}

// Lease represents a workflow execution lease
type Lease struct {
	WorkflowID string    `json:"workflow_id"`
	OwnerID    string    `json:"owner_id"`
	ExpiresAt  time.Time `json:"expires_at"`
}

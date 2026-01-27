package contd

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"time"

	"github.com/google/uuid"
)

// contextKey is the key type for context values
type contextKey string

const executionContextKey contextKey = "contd_execution_context"

// ExecutionContext holds the context for a running workflow
type ExecutionContext struct {
	WorkflowID   string
	OrgID        string
	WorkflowName string
	ExecutorID   string
	Tags         map[string]string

	state       *WorkflowState
	stepCounter int
	engine      Engine
	lease       *Lease

	heartbeatStop chan struct{}
	heartbeatWg   sync.WaitGroup
	mu            sync.RWMutex
}

// Engine interface for workflow execution
type Engine interface {
	Restore(workflowID string) (*WorkflowState, error)
	CompleteWorkflow(workflowID string) error
	MaybeSnapshot(state *WorkflowState) error
	LeaseManager() LeaseManager
	Journal() Journal
	Idempotency() IdempotencyManager
}

// LeaseManager interface for lease operations
type LeaseManager interface {
	Acquire(workflowID, ownerID string) (*Lease, error)
	Release(lease *Lease) error
	Heartbeat(lease *Lease) error
	HeartbeatInterval() time.Duration
}

// Journal interface for event logging
type Journal interface {
	Append(event interface{}) error
}

// IdempotencyManager interface for idempotency operations
type IdempotencyManager interface {
	CheckCompleted(workflowID, stepID string) (*WorkflowState, error)
	AllocateAttempt(workflowID, stepID string, lease *Lease) (int, error)
	MarkCompleted(workflowID, stepID string, attemptID int, state *WorkflowState) error
}

// Current returns the current execution context from the Go context
func Current(ctx context.Context) (*ExecutionContext, error) {
	ec, ok := ctx.Value(executionContextKey).(*ExecutionContext)
	if !ok || ec == nil {
		return nil, NewNoActiveWorkflow("No workflow context found. Did you forget to use WithContext?")
	}
	return ec, nil
}

// WithContext returns a new context with the execution context attached
func WithContext(ctx context.Context, ec *ExecutionContext) context.Context {
	return context.WithValue(ctx, executionContextKey, ec)
}

// NewExecutionContext creates a new execution context
func NewExecutionContext(workflowID, orgID, workflowName string, tags map[string]string) *ExecutionContext {
	if workflowID == "" {
		workflowID = "wf-" + uuid.New().String()
	}
	if orgID == "" {
		orgID = "default"
	}

	hostname, _ := os.Hostname()
	executorID := fmt.Sprintf("%s-%s", hostname, uuid.New().String()[:8])

	ec := &ExecutionContext{
		WorkflowID:   workflowID,
		OrgID:        orgID,
		WorkflowName: workflowName,
		ExecutorID:   executorID,
		Tags:         tags,
		stepCounter:  0,
	}

	// Initialize state for new workflows
	if workflowID == "" {
		ec.state = &WorkflowState{
			WorkflowID: ec.WorkflowID,
			StepNumber: 0,
			Variables:  make(map[string]interface{}),
			Metadata: map[string]interface{}{
				"workflow_name": workflowName,
				"started_at":    time.Now().UTC().Format(time.RFC3339),
				"tags":          tags,
			},
			Version:  "1.0",
			Checksum: "",
			OrgID:    orgID,
		}
		ec.state.Checksum = computeChecksum(ec.state)
	}

	return ec
}

// IsResuming returns true if the workflow is being resumed
func (ec *ExecutionContext) IsResuming() bool {
	ec.mu.RLock()
	defer ec.mu.RUnlock()
	return ec.state == nil
}

// GetState returns the current workflow state
func (ec *ExecutionContext) GetState() (*WorkflowState, error) {
	ec.mu.RLock()
	defer ec.mu.RUnlock()
	if ec.state == nil {
		return nil, fmt.Errorf("state not initialized")
	}
	return ec.state, nil
}

// SetState sets the workflow state
func (ec *ExecutionContext) SetState(state *WorkflowState) {
	ec.mu.Lock()
	defer ec.mu.Unlock()
	ec.state = state
	ec.stepCounter = state.StepNumber
}

// IncrementStep increments the step counter
func (ec *ExecutionContext) IncrementStep() {
	ec.mu.Lock()
	defer ec.mu.Unlock()
	ec.stepCounter++
}

// GenerateStepID generates a deterministic step ID
func (ec *ExecutionContext) GenerateStepID(stepName string) string {
	ec.mu.RLock()
	defer ec.mu.RUnlock()
	return fmt.Sprintf("%s_%d", stepName, ec.stepCounter)
}

// ExtractState extracts new state from a step result
func (ec *ExecutionContext) ExtractState(result interface{}) *WorkflowState {
	ec.mu.Lock()
	defer ec.mu.Unlock()

	// If result is already a WorkflowState, use it
	if state, ok := result.(*WorkflowState); ok {
		return state
	}

	currentVars := make(map[string]interface{})
	for k, v := range ec.state.Variables {
		currentVars[k] = v
	}

	// If result is a map, merge it
	if m, ok := result.(map[string]interface{}); ok {
		for k, v := range m {
			currentVars[k] = v
		}
	}

	newState := &WorkflowState{
		WorkflowID: ec.state.WorkflowID,
		StepNumber: ec.state.StepNumber + 1,
		Variables:  currentVars,
		Metadata:   ec.state.Metadata,
		Version:    ec.state.Version,
		Checksum:   "",
		OrgID:      ec.OrgID,
	}
	newState.Checksum = computeChecksum(newState)

	return newState
}

// SetEngine sets the execution engine
func (ec *ExecutionContext) SetEngine(engine Engine) {
	ec.mu.Lock()
	defer ec.mu.Unlock()
	ec.engine = engine
}

// GetEngine returns the execution engine
func (ec *ExecutionContext) GetEngine() Engine {
	ec.mu.RLock()
	defer ec.mu.RUnlock()
	return ec.engine
}

// SetLease sets the lease
func (ec *ExecutionContext) SetLease(lease *Lease) {
	ec.mu.Lock()
	defer ec.mu.Unlock()
	ec.lease = lease
}

// GetLease returns the lease
func (ec *ExecutionContext) GetLease() *Lease {
	ec.mu.RLock()
	defer ec.mu.RUnlock()
	return ec.lease
}

// StartHeartbeat starts the background heartbeat goroutine
func (ec *ExecutionContext) StartHeartbeat(lease *Lease, engine Engine) {
	ec.mu.Lock()
	ec.lease = lease
	ec.engine = engine
	ec.heartbeatStop = make(chan struct{})
	ec.mu.Unlock()

	ec.heartbeatWg.Add(1)
	go func() {
		defer ec.heartbeatWg.Done()
		ticker := time.NewTicker(engine.LeaseManager().HeartbeatInterval())
		defer ticker.Stop()

		for {
			select {
			case <-ec.heartbeatStop:
				return
			case <-ticker.C:
				if err := engine.LeaseManager().Heartbeat(lease); err != nil {
					fmt.Printf("Heartbeat failed for %s: %v\n", ec.WorkflowID, err)
					return
				}
			}
		}
	}()
}

// StopHeartbeat stops the background heartbeat goroutine
func (ec *ExecutionContext) StopHeartbeat() {
	ec.mu.Lock()
	if ec.heartbeatStop != nil {
		close(ec.heartbeatStop)
		ec.heartbeatStop = nil
	}
	ec.mu.Unlock()
	ec.heartbeatWg.Wait()
}

// CreateSavepoint creates a rich savepoint with epistemic metadata
func (ec *ExecutionContext) CreateSavepoint(metadata *SavepointMetadata) (string, error) {
	savepointID := uuid.New().String()

	ec.mu.RLock()
	state := ec.state
	engine := ec.engine
	ec.mu.RUnlock()

	if metadata == nil {
		if m, ok := state.Variables["_savepoint_metadata"].(map[string]interface{}); ok {
			metadata = &SavepointMetadata{
				GoalSummary: getString(m, "goal_summary"),
				Hypotheses:  getStringSlice(m, "hypotheses"),
				Questions:   getStringSlice(m, "questions"),
				NextStep:    getString(m, "next_step"),
			}
		} else {
			metadata = &SavepointMetadata{}
		}
	}

	if engine != nil {
		event := map[string]interface{}{
			"event_id":            uuid.New().String(),
			"workflow_id":         ec.WorkflowID,
			"org_id":              ec.OrgID,
			"timestamp":           time.Now().UTC().Format(time.RFC3339),
			"event_type":          "savepoint_created",
			"savepoint_id":        savepointID,
			"step_number":         state.StepNumber,
			"goal_summary":        metadata.GoalSummary,
			"current_hypotheses":  metadata.Hypotheses,
			"open_questions":      metadata.Questions,
			"decision_log":        metadata.Decisions,
			"next_step":           metadata.NextStep,
			"snapshot_ref":        "",
		}
		if err := engine.Journal().Append(event); err != nil {
			return "", err
		}
	}

	fmt.Printf("Created savepoint %s at step %d\n", savepointID, state.StepNumber)
	return savepointID, nil
}

// UpdateTags updates workflow tags
func (ec *ExecutionContext) UpdateTags(newTags map[string]string) {
	ec.mu.Lock()
	defer ec.mu.Unlock()

	if ec.Tags == nil {
		ec.Tags = make(map[string]string)
	}
	for k, v := range newTags {
		ec.Tags[k] = v
	}

	if ec.state != nil {
		metadata := ec.state.Metadata
		if metadata == nil {
			metadata = make(map[string]interface{})
		}
		tags, _ := metadata["tags"].(map[string]string)
		if tags == nil {
			tags = make(map[string]string)
		}
		for k, v := range newTags {
			tags[k] = v
		}
		metadata["tags"] = tags
		ec.state.Metadata = metadata
	}
}

func computeChecksum(state *WorkflowState) string {
	data, _ := json.Marshal(state)
	hash := sha256.Sum256(data)
	return hex.EncodeToString(hash[:])
}

func getString(m map[string]interface{}, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

func getStringSlice(m map[string]interface{}, key string) []string {
	if v, ok := m[key].([]interface{}); ok {
		result := make([]string, len(v))
		for i, item := range v {
			result[i], _ = item.(string)
		}
		return result
	}
	return nil
}

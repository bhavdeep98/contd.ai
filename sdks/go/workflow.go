package contd

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
)

// WorkflowFunc is the signature for workflow functions
type WorkflowFunc func(ctx context.Context, input interface{}) (interface{}, error)

// StepFunc is the signature for step functions
type StepFunc func(ctx context.Context, input interface{}) (interface{}, error)

// WorkflowRunner executes workflows with the Contd runtime
type WorkflowRunner struct {
	engine Engine
	config WorkflowConfig
}

// NewWorkflowRunner creates a new workflow runner
func NewWorkflowRunner(engine Engine, config WorkflowConfig) *WorkflowRunner {
	return &WorkflowRunner{
		engine: engine,
		config: config,
	}
}

// Run executes a workflow function
func (r *WorkflowRunner) Run(ctx context.Context, workflowName string, fn WorkflowFunc, input interface{}) (interface{}, error) {
	startTime := time.Now()

	// Create execution context
	ec := NewExecutionContext(r.config.WorkflowID, r.config.OrgID, workflowName, r.config.Tags)
	ec.SetEngine(r.engine)

	// Acquire lease
	lease, err := r.engine.LeaseManager().Acquire(ec.WorkflowID, ec.ExecutorID)
	if err != nil {
		return nil, err
	}
	if lease == nil {
		return nil, NewWorkflowLocked(ec.WorkflowID, "", "")
	}
	ec.SetLease(lease)

	defer func() {
		ec.StopHeartbeat()
		r.engine.LeaseManager().Release(lease)
	}()

	// Start heartbeat
	ec.StartHeartbeat(lease, r.engine)

	// Check if resuming
	if ec.IsResuming() {
		state, err := r.engine.Restore(ec.WorkflowID)
		if err != nil {
			return nil, err
		}
		ec.SetState(state)
		fmt.Printf("Resumed workflow %s from step %d\n", ec.WorkflowID, state.StepNumber)
	}

	// Execute workflow with context
	workflowCtx := WithContext(ctx, ec)
	result, err := fn(workflowCtx, input)
	if err != nil {
		return nil, err
	}

	// Mark complete
	if err := r.engine.CompleteWorkflow(ec.WorkflowID); err != nil {
		return nil, err
	}

	duration := time.Since(startTime)
	fmt.Printf("Workflow %s completed in %v\n", ec.WorkflowID, duration)

	return result, nil
}

// StepRunner executes steps within a workflow
type StepRunner struct {
	config StepConfig
}

// NewStepRunner creates a new step runner
func NewStepRunner(config StepConfig) *StepRunner {
	return &StepRunner{config: config}
}

// Run executes a step function
func (r *StepRunner) Run(ctx context.Context, stepName string, fn StepFunc, input interface{}) (interface{}, error) {
	ec, err := Current(ctx)
	if err != nil {
		return nil, err
	}

	engine := ec.GetEngine()
	if engine == nil {
		return nil, fmt.Errorf("no execution engine in context")
	}

	lease := ec.GetLease()
	stepID := ec.GenerateStepID(stepName)

	// Check idempotency
	cachedResult, err := engine.Idempotency().CheckCompleted(ec.WorkflowID, stepID)
	if err != nil {
		return nil, err
	}
	if cachedResult != nil {
		fmt.Printf("Step %s already completed, returning cached result\n", stepID)
		ec.SetState(cachedResult)
		return cachedResult, nil
	}

	// Allocate attempt
	attemptID, err := engine.Idempotency().AllocateAttempt(ec.WorkflowID, stepID, lease)
	if err != nil {
		return nil, err
	}

	// Write intention
	if err := engine.Journal().Append(map[string]interface{}{
		"event_id":    uuid.New().String(),
		"workflow_id": ec.WorkflowID,
		"org_id":      ec.OrgID,
		"timestamp":   time.Now().UTC().Format(time.RFC3339),
		"event_type":  "step_intention",
		"step_id":     stepID,
		"step_name":   stepName,
		"attempt_id":  attemptID,
	}); err != nil {
		return nil, err
	}

	// Execute with timeout
	startTime := time.Now()
	var result interface{}
	var execErr error

	if r.config.Timeout > 0 {
		result, execErr = r.executeWithTimeout(ctx, fn, input, r.config.Timeout, ec.WorkflowID, stepID, stepName)
	} else {
		result, execErr = fn(ctx, input)
	}

	durationMs := time.Since(startTime).Milliseconds()

	if execErr != nil {
		// Log failure
		engine.Journal().Append(map[string]interface{}{
			"event_id":    uuid.New().String(),
			"workflow_id": ec.WorkflowID,
			"org_id":      ec.OrgID,
			"timestamp":   time.Now().UTC().Format(time.RFC3339),
			"event_type":  "step_failed",
			"step_id":     stepID,
			"attempt_id":  attemptID,
			"error":       execErr.Error(),
		})

		// Check retry policy
		if r.config.Retry != nil && r.config.Retry.ShouldRetry(attemptID, execErr) {
			backoff := r.config.Retry.Backoff(attemptID)
			fmt.Printf("Retrying step %s, attempt %d after %v\n", stepID, attemptID+1, backoff)
			time.Sleep(backoff)
			return r.Run(ctx, stepName, fn, input)
		}

		// Check max attempts
		if r.config.Retry != nil && attemptID >= r.config.Retry.MaxAttempts {
			return nil, NewTooManyAttempts(ec.WorkflowID, stepID, stepName, r.config.Retry.MaxAttempts, execErr.Error())
		}

		return nil, NewStepExecutionFailed(ec.WorkflowID, stepID, stepName, attemptID, execErr)
	}

	// Extract new state
	newState := ec.ExtractState(result)
	oldState, _ := ec.GetState()

	// Compute delta
	delta := computeDelta(oldState, newState)

	// Write completion
	if err := engine.Journal().Append(map[string]interface{}{
		"event_id":    uuid.New().String(),
		"workflow_id": ec.WorkflowID,
		"org_id":      ec.OrgID,
		"timestamp":   time.Now().UTC().Format(time.RFC3339),
		"event_type":  "step_completed",
		"step_id":     stepID,
		"attempt_id":  attemptID,
		"state_delta": delta,
		"duration_ms": durationMs,
	}); err != nil {
		return nil, err
	}

	// Mark completed
	if err := engine.Idempotency().MarkCompleted(ec.WorkflowID, stepID, attemptID, newState); err != nil {
		return nil, err
	}

	// Update context
	ec.SetState(newState)
	ec.IncrementStep()

	// Checkpoint if configured
	if r.config.Checkpoint {
		if err := engine.MaybeSnapshot(newState); err != nil {
			return nil, err
		}
	}

	// Savepoint if configured
	if r.config.Savepoint {
		if _, err := ec.CreateSavepoint(nil); err != nil {
			return nil, err
		}
	}

	return result, nil
}

func (r *StepRunner) executeWithTimeout(ctx context.Context, fn StepFunc, input interface{}, timeout time.Duration, workflowID, stepID, stepName string) (interface{}, error) {
	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	resultCh := make(chan interface{}, 1)
	errCh := make(chan error, 1)

	go func() {
		result, err := fn(ctx, input)
		if err != nil {
			errCh <- err
		} else {
			resultCh <- result
		}
	}()

	select {
	case result := <-resultCh:
		return result, nil
	case err := <-errCh:
		return nil, err
	case <-ctx.Done():
		return nil, NewStepTimeout(workflowID, stepID, stepName, timeout.Seconds(), timeout.Seconds())
	}
}

func computeDelta(oldState, newState *WorkflowState) map[string]interface{} {
	delta := make(map[string]interface{})

	if oldState == nil {
		return newState.Variables
	}

	// Find changed/added keys
	for k, v := range newState.Variables {
		if oldV, exists := oldState.Variables[k]; !exists || !equal(oldV, v) {
			delta[k] = v
		}
	}

	// Find removed keys
	for k := range oldState.Variables {
		if _, exists := newState.Variables[k]; !exists {
			delta[k] = nil
		}
	}

	return delta
}

func equal(a, b interface{}) bool {
	// Simple equality check - could be improved
	return fmt.Sprintf("%v", a) == fmt.Sprintf("%v", b)
}

package contd

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
)

// StepExecution records a step execution during testing
type StepExecution struct {
	StepName    string
	StepID      string
	Attempt     int
	StartedAt   time.Time
	CompletedAt *time.Time
	DurationMs  int64
	Result      interface{}
	Error       string
	WasCached   bool
}

// WorkflowExecution records a workflow execution during testing
type WorkflowExecution struct {
	WorkflowID        string
	WorkflowName      string
	StartedAt         time.Time
	CompletedAt       *time.Time
	Status            string
	Steps             []StepExecution
	FinalState        *WorkflowState
	Error             string
	InterruptedAtStep *int
}

// MockEngine is a mock execution engine for testing
type MockEngine struct {
	mu              sync.RWMutex
	interruptAtStep *int
	failAtStep      *int
	failWith        error
	recordedEvents  []interface{}
	stepCounter     int
	states          map[string]*WorkflowState
	completedSteps  map[string]*WorkflowState

	leaseManager      *MockLeaseManager
	journal           *MockJournal
	idempotencyMgr    *MockIdempotencyManager
}

// NewMockEngine creates a new mock engine
func NewMockEngine() *MockEngine {
	engine := &MockEngine{
		recordedEvents: make([]interface{}, 0),
		states:         make(map[string]*WorkflowState),
		completedSteps: make(map[string]*WorkflowState),
	}
	engine.leaseManager = &MockLeaseManager{engine: engine}
	engine.journal = &MockJournal{engine: engine}
	engine.idempotencyMgr = &MockIdempotencyManager{engine: engine}
	return engine
}

// Restore restores workflow state
func (e *MockEngine) Restore(workflowID string) (*WorkflowState, error) {
	e.mu.RLock()
	defer e.mu.RUnlock()
	if state, ok := e.states[workflowID]; ok {
		return state, nil
	}
	return &WorkflowState{
		WorkflowID: workflowID,
		StepNumber: 0,
		Variables:  make(map[string]interface{}),
		Metadata:   make(map[string]interface{}),
		Version:    "1.0",
		OrgID:      "default",
	}, nil
}

// CompleteWorkflow marks a workflow as complete
func (e *MockEngine) CompleteWorkflow(workflowID string) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	if state, ok := e.states[workflowID]; ok {
		state.Metadata["completed_at"] = time.Now().UTC().Format(time.RFC3339)
	}
	return nil
}

// MaybeSnapshot stores a snapshot
func (e *MockEngine) MaybeSnapshot(state *WorkflowState) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.states[state.WorkflowID] = state
	return nil
}

// LeaseManager returns the lease manager
func (e *MockEngine) LeaseManager() LeaseManager {
	return e.leaseManager
}

// Journal returns the journal
func (e *MockEngine) Journal() Journal {
	return e.journal
}

// Idempotency returns the idempotency manager
func (e *MockEngine) Idempotency() IdempotencyManager {
	return e.idempotencyMgr
}

// SetInterruptAt configures interruption at a specific step
func (e *MockEngine) SetInterruptAt(stepNumber int) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.interruptAtStep = &stepNumber
}

// SetFailAt configures failure injection at a specific step
func (e *MockEngine) SetFailAt(stepNumber int, err error) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.failAtStep = &stepNumber
	e.failWith = err
}

// CheckInterrupt checks if workflow should be interrupted
func (e *MockEngine) CheckInterrupt(stepNumber int, workflowID string) error {
	e.mu.RLock()
	defer e.mu.RUnlock()
	if e.interruptAtStep != nil && stepNumber >= *e.interruptAtStep {
		return NewWorkflowInterrupted(workflowID, stepNumber)
	}
	return nil
}

// CheckFailure checks if failure should be injected
func (e *MockEngine) CheckFailure(stepNumber int) error {
	e.mu.RLock()
	defer e.mu.RUnlock()
	if e.failAtStep != nil && stepNumber == *e.failAtStep {
		if e.failWith != nil {
			return e.failWith
		}
		return fmt.Errorf("injected failure at step %d", stepNumber)
	}
	return nil
}

// GetRecordedEvents returns recorded events
func (e *MockEngine) GetRecordedEvents() []interface{} {
	e.mu.RLock()
	defer e.mu.RUnlock()
	result := make([]interface{}, len(e.recordedEvents))
	copy(result, e.recordedEvents)
	return result
}

// ClearRecordedEvents clears recorded events
func (e *MockEngine) ClearRecordedEvents() {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.recordedEvents = make([]interface{}, 0)
}

// Reset resets all mock state
func (e *MockEngine) Reset() {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.interruptAtStep = nil
	e.failAtStep = nil
	e.failWith = nil
	e.recordedEvents = make([]interface{}, 0)
	e.stepCounter = 0
	e.states = make(map[string]*WorkflowState)
	e.completedSteps = make(map[string]*WorkflowState)
}

// MockLeaseManager is a mock lease manager
type MockLeaseManager struct {
	engine *MockEngine
}

func (m *MockLeaseManager) Acquire(workflowID, ownerID string) (*Lease, error) {
	return &Lease{
		WorkflowID: workflowID,
		OwnerID:    ownerID,
		ExpiresAt:  time.Now().Add(time.Minute),
	}, nil
}

func (m *MockLeaseManager) Release(lease *Lease) error {
	return nil
}

func (m *MockLeaseManager) Heartbeat(lease *Lease) error {
	return nil
}

func (m *MockLeaseManager) HeartbeatInterval() time.Duration {
	return 10 * time.Second
}

// MockJournal is a mock journal
type MockJournal struct {
	engine *MockEngine
}

func (m *MockJournal) Append(event interface{}) error {
	m.engine.mu.Lock()
	defer m.engine.mu.Unlock()
	m.engine.recordedEvents = append(m.engine.recordedEvents, event)
	return nil
}

// MockIdempotencyManager is a mock idempotency manager
type MockIdempotencyManager struct {
	engine *MockEngine
}

func (m *MockIdempotencyManager) CheckCompleted(workflowID, stepID string) (*WorkflowState, error) {
	m.engine.mu.RLock()
	defer m.engine.mu.RUnlock()
	key := fmt.Sprintf("%s:%s", workflowID, stepID)
	return m.engine.completedSteps[key], nil
}

func (m *MockIdempotencyManager) AllocateAttempt(workflowID, stepID string, lease *Lease) (int, error) {
	m.engine.mu.Lock()
	defer m.engine.mu.Unlock()
	m.engine.stepCounter++
	return m.engine.stepCounter, nil
}

func (m *MockIdempotencyManager) MarkCompleted(workflowID, stepID string, attemptID int, state *WorkflowState) error {
	m.engine.mu.Lock()
	defer m.engine.mu.Unlock()
	key := fmt.Sprintf("%s:%s", workflowID, stepID)
	m.engine.completedSteps[key] = state
	return nil
}

// TestCase is a test harness for workflow testing
type TestCase struct {
	Engine           *MockEngine
	Executions       []WorkflowExecution
	CurrentExecution *WorkflowExecution
}

// NewTestCase creates a new test case
func NewTestCase() *TestCase {
	return &TestCase{
		Engine:     NewMockEngine(),
		Executions: make([]WorkflowExecution, 0),
	}
}

// SetUp sets up test fixtures
func (tc *TestCase) SetUp() {
	tc.Engine.Reset()
	tc.Executions = make([]WorkflowExecution, 0)
	tc.CurrentExecution = nil
}

// TearDown tears down test fixtures
func (tc *TestCase) TearDown() {
	tc.Engine.Reset()
}

// RunWorkflowOptions contains options for running a workflow in tests
type RunWorkflowOptions struct {
	Input           interface{}
	InterruptAtStep *int
	FailAtStep      *int
	FailWith        error
}

// RunWorkflow runs a workflow with optional interruption or failure injection
func (tc *TestCase) RunWorkflow(ctx context.Context, workflowName string, fn WorkflowFunc, opts RunWorkflowOptions) (interface{}, error) {
	// Configure mock engine
	if opts.InterruptAtStep != nil {
		tc.Engine.SetInterruptAt(*opts.InterruptAtStep)
	}
	if opts.FailAtStep != nil {
		tc.Engine.SetFailAt(*opts.FailAtStep, opts.FailWith)
	}

	// Create execution record
	execution := WorkflowExecution{
		WorkflowID:   "wf-" + uuid.New().String(),
		WorkflowName: workflowName,
		StartedAt:    time.Now(),
		Status:       "running",
		Steps:        make([]StepExecution, 0),
	}
	tc.CurrentExecution = &execution
	tc.Executions = append(tc.Executions, execution)

	// Run workflow
	runner := NewWorkflowRunner(tc.Engine, WorkflowConfig{})
	result, err := runner.Run(ctx, workflowName, fn, opts.Input)

	if err != nil {
		if _, ok := err.(*WorkflowInterrupted); ok {
			execution.Status = "interrupted"
			if ie, ok := err.(*WorkflowInterrupted); ok {
				execution.InterruptedAtStep = &ie.StepNumber
			}
			return nil, nil
		}
		execution.Status = "failed"
		execution.Error = err.Error()
		now := time.Now()
		execution.CompletedAt = &now
		return nil, err
	}

	execution.Status = "completed"
	now := time.Now()
	execution.CompletedAt = &now
	return result, nil
}

// ResumeWorkflow resumes an interrupted workflow
func (tc *TestCase) ResumeWorkflow(ctx context.Context, workflowName string, fn WorkflowFunc, input interface{}) (interface{}, error) {
	tc.Engine.Reset()
	return tc.RunWorkflow(ctx, workflowName, fn, RunWorkflowOptions{Input: input})
}

// AssertCompleted asserts that the last workflow completed
func (tc *TestCase) AssertCompleted() error {
	if tc.CurrentExecution == nil {
		return fmt.Errorf("no workflow execution to check")
	}
	if tc.CurrentExecution.Status != "completed" {
		return fmt.Errorf("workflow not completed: status=%s", tc.CurrentExecution.Status)
	}
	return nil
}

// AssertInterrupted asserts that the last workflow was interrupted
func (tc *TestCase) AssertInterrupted(atStep *int) error {
	if tc.CurrentExecution == nil {
		return fmt.Errorf("no workflow execution to check")
	}
	if tc.CurrentExecution.Status != "interrupted" {
		return fmt.Errorf("workflow not interrupted: status=%s", tc.CurrentExecution.Status)
	}
	if atStep != nil && (tc.CurrentExecution.InterruptedAtStep == nil || *tc.CurrentExecution.InterruptedAtStep != *atStep) {
		return fmt.Errorf("interrupted at wrong step: expected=%d, actual=%v", *atStep, tc.CurrentExecution.InterruptedAtStep)
	}
	return nil
}

// AssertFailed asserts that the last workflow failed
func (tc *TestCase) AssertFailed(errorContains string) error {
	if tc.CurrentExecution == nil {
		return fmt.Errorf("no workflow execution to check")
	}
	if tc.CurrentExecution.Status != "failed" {
		return fmt.Errorf("workflow not failed: status=%s", tc.CurrentExecution.Status)
	}
	if errorContains != "" && tc.CurrentExecution.Error == "" {
		return fmt.Errorf("error message doesn't contain '%s': actual='%s'", errorContains, tc.CurrentExecution.Error)
	}
	return nil
}

// GetEvents returns recorded events
func (tc *TestCase) GetEvents(eventType string) []interface{} {
	events := tc.Engine.GetRecordedEvents()
	if eventType == "" {
		return events
	}
	filtered := make([]interface{}, 0)
	for _, e := range events {
		if m, ok := e.(map[string]interface{}); ok {
			if m["event_type"] == eventType {
				filtered = append(filtered, e)
			}
		}
	}
	return filtered
}

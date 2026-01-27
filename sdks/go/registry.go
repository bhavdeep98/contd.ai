package contd

import (
	"sync"
)

// Registry holds registered workflows
type Registry struct {
	mu        sync.RWMutex
	workflows map[string]WorkflowFunc
}

// GlobalRegistry is the default workflow registry
var GlobalRegistry = NewRegistry()

// NewRegistry creates a new workflow registry
func NewRegistry() *Registry {
	return &Registry{
		workflows: make(map[string]WorkflowFunc),
	}
}

// Register registers a workflow function
func (r *Registry) Register(name string, fn WorkflowFunc) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.workflows[name] = fn
}

// Get retrieves a workflow function by name
func (r *Registry) Get(name string) (WorkflowFunc, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	fn, ok := r.workflows[name]
	return fn, ok
}

// Has checks if a workflow is registered
func (r *Registry) Has(name string) bool {
	r.mu.RLock()
	defer r.mu.RUnlock()
	_, ok := r.workflows[name]
	return ok
}

// Names returns all registered workflow names
func (r *Registry) Names() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()
	names := make([]string, 0, len(r.workflows))
	for name := range r.workflows {
		names = append(names, name)
	}
	return names
}

// Clear removes all registered workflows
func (r *Registry) Clear() {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.workflows = make(map[string]WorkflowFunc)
}

// RegisterWorkflow registers a workflow in the global registry
func RegisterWorkflow(name string, fn WorkflowFunc) {
	GlobalRegistry.Register(name, fn)
}

// GetWorkflow retrieves a workflow from the global registry
func GetWorkflow(name string) (WorkflowFunc, bool) {
	return GlobalRegistry.Get(name)
}

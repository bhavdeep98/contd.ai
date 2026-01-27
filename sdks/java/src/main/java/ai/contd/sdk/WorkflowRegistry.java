package ai.contd.sdk;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Function;

/**
 * Central registry for workflow functions
 */
public class WorkflowRegistry {
    private static final WorkflowRegistry INSTANCE = new WorkflowRegistry();
    private final Map<String, Function<Object, ?>> workflows = new ConcurrentHashMap<>();

    private WorkflowRegistry() {}

    /**
     * Get the global registry instance
     */
    public static WorkflowRegistry getInstance() {
        return INSTANCE;
    }

    /**
     * Register a workflow function
     */
    public void register(String name, Function<Object, ?> fn) {
        workflows.put(name, fn);
    }

    /**
     * Get a workflow function by name
     */
    public Optional<Function<Object, ?>> get(String name) {
        return Optional.ofNullable(workflows.get(name));
    }

    /**
     * Check if a workflow is registered
     */
    public boolean has(String name) {
        return workflows.containsKey(name);
    }

    /**
     * Get all registered workflow names
     */
    public Set<String> names() {
        return new HashSet<>(workflows.keySet());
    }

    /**
     * Clear all registered workflows
     */
    public void clear() {
        workflows.clear();
    }

    /**
     * Get all registered workflows
     */
    public Map<String, Function<Object, ?>> listAll() {
        return new HashMap<>(workflows);
    }
}

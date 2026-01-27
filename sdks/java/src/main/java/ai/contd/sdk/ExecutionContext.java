package ai.contd.sdk;

import ai.contd.sdk.errors.NoActiveWorkflowException;
import ai.contd.sdk.types.*;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.net.InetAddress;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Execution context for a running workflow
 */
public class ExecutionContext {
    private static final ThreadLocal<ExecutionContext> CURRENT = new ThreadLocal<>();
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();

    private final String workflowId;
    private final String orgId;
    private final String workflowName;
    private final String executorId;
    private Map<String, String> tags;

    private WorkflowState state;
    private final AtomicInteger stepCounter = new AtomicInteger(0);
    private Engine engine;
    private Lease lease;

    private ScheduledExecutorService heartbeatExecutor;
    private ScheduledFuture<?> heartbeatFuture;

    public ExecutionContext(String workflowId, String orgId, String workflowName,
                            String executorId, Map<String, String> tags) {
        this.workflowId = workflowId;
        this.orgId = orgId;
        this.workflowName = workflowName;
        this.executorId = executorId;
        this.tags = tags != null ? new HashMap<>(tags) : new HashMap<>();
    }

    /**
     * Get current execution context
     */
    public static ExecutionContext current() {
        ExecutionContext ctx = CURRENT.get();
        if (ctx == null) {
            throw new NoActiveWorkflowException("No workflow context found. Did you forget @Workflow annotation?");
        }
        return ctx;
    }

    /**
     * Set current execution context
     */
    public static void setCurrent(ExecutionContext ctx) {
        CURRENT.set(ctx);
    }

    /**
     * Clear current execution context
     */
    public static void clear() {
        CURRENT.remove();
    }

    /**
     * Create new context or prepare for resume
     */
    public static ExecutionContext getOrCreate(String workflowId, String workflowName,
                                               String orgId, Map<String, String> tags) {
        String id = workflowId != null ? workflowId : "wf-" + UUID.randomUUID();
        String org = orgId != null ? orgId : "default";
        String executorId = generateExecutorId();

        ExecutionContext ctx = new ExecutionContext(id, org, workflowName, executorId, tags);

        if (workflowId == null) {
            // New workflow - create initial state
            Map<String, Object> metadata = new HashMap<>();
            metadata.put("workflow_name", workflowName);
            metadata.put("started_at", Instant.now().toString());
            metadata.put("tags", tags != null ? tags : new HashMap<>());

            WorkflowState initialState = WorkflowState.builder()
                    .workflowId(id)
                    .stepNumber(0)
                    .variables(new HashMap<>())
                    .metadata(metadata)
                    .version("1.0")
                    .orgId(org)
                    .build();
            initialState.setChecksum(computeChecksum(initialState));
            ctx.state = initialState;
        }

        CURRENT.set(ctx);
        return ctx;
    }

    private static String generateExecutorId() {
        try {
            String hostname = InetAddress.getLocalHost().getHostName();
            return hostname + "-" + UUID.randomUUID().toString().substring(0, 8);
        } catch (Exception e) {
            return "unknown-" + UUID.randomUUID().toString().substring(0, 8);
        }
    }

    private static String computeChecksum(WorkflowState state) {
        try {
            String json = OBJECT_MAPPER.writeValueAsString(state);
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(json.getBytes(StandardCharsets.UTF_8));
            StringBuilder hexString = new StringBuilder();
            for (byte b : hash) {
                String hex = Integer.toHexString(0xff & b);
                if (hex.length() == 1) hexString.append('0');
                hexString.append(hex);
            }
            return hexString.toString();
        } catch (Exception e) {
            return "";
        }
    }

    // Getters
    public String getWorkflowId() { return workflowId; }
    public String getOrgId() { return orgId; }
    public String getWorkflowName() { return workflowName; }
    public String getExecutorId() { return executorId; }
    public Map<String, String> getTags() { return tags; }

    public boolean isResuming() {
        return state == null;
    }

    public WorkflowState getState() {
        if (state == null) {
            throw new IllegalStateException("State not initialized");
        }
        return state;
    }

    public void setState(WorkflowState state) {
        this.state = state;
        this.stepCounter.set(state.getStepNumber());
    }

    public void incrementStep() {
        stepCounter.incrementAndGet();
    }

    public String generateStepId(String stepName) {
        return stepName + "_" + stepCounter.get();
    }

    public WorkflowState extractState(Object result) {
        if (result instanceof WorkflowState ws) {
            return ws;
        }

        Map<String, Object> currentVars = new HashMap<>(state.getVariables());

        if (result instanceof Map<?, ?> map) {
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                currentVars.put(entry.getKey().toString(), entry.getValue());
            }
        }

        WorkflowState newState = WorkflowState.builder()
                .workflowId(state.getWorkflowId())
                .stepNumber(state.getStepNumber() + 1)
                .variables(currentVars)
                .metadata(state.getMetadata())
                .version(state.getVersion())
                .orgId(orgId)
                .build();
        newState.setChecksum(computeChecksum(newState));

        return newState;
    }

    public void setEngine(Engine engine) {
        this.engine = engine;
    }

    public Engine getEngine() {
        return engine;
    }

    public void setLease(Lease lease) {
        this.lease = lease;
    }

    public Lease getLease() {
        return lease;
    }

    public void startHeartbeat(Lease lease, Engine engine) {
        this.lease = lease;
        this.engine = engine;

        heartbeatExecutor = Executors.newSingleThreadScheduledExecutor();
        heartbeatFuture = heartbeatExecutor.scheduleAtFixedRate(() -> {
            try {
                engine.getLeaseManager().heartbeat(lease);
            } catch (Exception e) {
                System.err.println("Heartbeat failed for " + workflowId + ": " + e.getMessage());
                stopHeartbeat();
            }
        }, 0, engine.getLeaseManager().getHeartbeatInterval().toMillis(), TimeUnit.MILLISECONDS);
    }

    public void stopHeartbeat() {
        if (heartbeatFuture != null) {
            heartbeatFuture.cancel(false);
        }
        if (heartbeatExecutor != null) {
            heartbeatExecutor.shutdown();
        }
    }

    public String createSavepoint(SavepointMetadata metadata) {
        String savepointId = UUID.randomUUID().toString();

        if (metadata == null) {
            Object savedMetadata = state.getVariables().get("_savepoint_metadata");
            if (savedMetadata instanceof Map<?, ?> m) {
                metadata = SavepointMetadata.builder()
                        .goalSummary((String) m.getOrDefault("goal_summary", ""))
                        .nextStep((String) m.getOrDefault("next_step", ""))
                        .build();
            } else {
                metadata = new SavepointMetadata();
            }
        }

        if (engine != null) {
            Map<String, Object> event = new HashMap<>();
            event.put("event_id", UUID.randomUUID().toString());
            event.put("workflow_id", workflowId);
            event.put("org_id", orgId);
            event.put("timestamp", Instant.now().toString());
            event.put("event_type", "savepoint_created");
            event.put("savepoint_id", savepointId);
            event.put("step_number", state.getStepNumber());
            event.put("goal_summary", metadata.getGoalSummary());
            event.put("current_hypotheses", metadata.getHypotheses());
            event.put("open_questions", metadata.getQuestions());
            event.put("decision_log", metadata.getDecisions());
            event.put("next_step", metadata.getNextStep());
            event.put("snapshot_ref", "");
            engine.getJournal().append(event);
        }

        System.out.println("Created savepoint " + savepointId + " at step " + state.getStepNumber());
        return savepointId;
    }

    public void updateTags(Map<String, String> newTags) {
        if (tags == null) {
            tags = new HashMap<>();
        }
        tags.putAll(newTags);

        if (state != null) {
            Map<String, Object> metadata = new HashMap<>(state.getMetadata());
            @SuppressWarnings("unchecked")
            Map<String, String> currentTags = (Map<String, String>) metadata.getOrDefault("tags", new HashMap<>());
            currentTags.putAll(newTags);
            metadata.put("tags", currentTags);
            state.setMetadata(metadata);
        }
    }
}

package ai.contd.sdk;

import ai.contd.sdk.errors.ContdException;
import ai.contd.sdk.errors.WorkflowLockedException;
import ai.contd.sdk.errors.WorkflowNotFoundException;
import ai.contd.sdk.types.*;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import okhttp3.*;

import java.io.IOException;
import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * HTTP client for remote workflow execution
 */
public class ContdClient {
    private final String apiKey;
    private final String baseUrl;
    private final OkHttpClient httpClient;
    private final ObjectMapper objectMapper;

    public ContdClient(String apiKey) {
        this(apiKey, "https://api.contd.ai", Duration.ofSeconds(30));
    }

    public ContdClient(String apiKey, String baseUrl, Duration timeout) {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
        this.httpClient = new OkHttpClient.Builder()
                .connectTimeout(timeout.toMillis(), TimeUnit.MILLISECONDS)
                .readTimeout(timeout.toMillis(), TimeUnit.MILLISECONDS)
                .writeTimeout(timeout.toMillis(), TimeUnit.MILLISECONDS)
                .build();
        this.objectMapper = new ObjectMapper()
                .registerModule(new JavaTimeModule())
                .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
                .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
    }

    /**
     * Start a new workflow
     */
    public String startWorkflow(String workflowName, Map<String, Object> input, WorkflowConfig config) throws IOException {
        Map<String, Object> body = new HashMap<>();
        body.put("workflow_name", workflowName);
        body.put("input", input);
        if (config != null) {
            body.put("config", config);
        }

        try (Response response = doRequest("POST", "/v1/workflows", body)) {
            Map<String, Object> result = parseResponse(response);
            return (String) result.get("workflow_id");
        }
    }

    /**
     * Get workflow status
     */
    public WorkflowStatusResponse getStatus(String workflowId) throws IOException {
        try (Response response = doRequest("GET", "/v1/workflows/" + workflowId, null)) {
            ResponseBody body = response.body();
            if (body == null) {
                throw new IOException("Empty response body");
            }
            return objectMapper.readValue(body.string(), WorkflowStatusResponse.class);
        }
    }

    /**
     * Resume an interrupted workflow
     */
    public String resume(String workflowId) throws IOException {
        try (Response response = doRequest("POST", "/v1/workflows/" + workflowId + "/resume", null)) {
            Map<String, Object> result = parseResponse(response);
            return (String) result.get("status");
        }
    }

    /**
     * Cancel a running workflow
     */
    public void cancel(String workflowId) throws IOException {
        try (Response response = doRequest("POST", "/v1/workflows/" + workflowId + "/cancel", null)) {
            // Response consumed and closed by try-with-resources
        }
    }

    /**
     * Get all savepoints for a workflow
     */
    @SuppressWarnings("unchecked")
    public List<SavepointInfo> getSavepoints(String workflowId) throws IOException {
        try (Response response = doRequest("GET", "/v1/workflows/" + workflowId + "/savepoints", null)) {
            Map<String, Object> result = parseResponse(response);
            List<Map<String, Object>> savepoints = (List<Map<String, Object>>) result.get("savepoints");
            return savepoints.stream()
                    .map(sp -> objectMapper.convertValue(sp, SavepointInfo.class))
                    .toList();
        }
    }

    /**
     * Time travel to a specific savepoint
     */
    public String timeTravel(String workflowId, String savepointId) throws IOException {
        Map<String, Object> body = Map.of("savepoint_id", savepointId);
        try (Response response = doRequest("POST", "/v1/workflows/" + workflowId + "/time-travel", body)) {
            Map<String, Object> result = parseResponse(response);
            return (String) result.get("new_workflow_id");
        }
    }

    /**
     * Health check
     */
    public HealthCheck health() throws IOException {
        try (Response response = doRequest("GET", "/health", null)) {
            ResponseBody body = response.body();
            if (body == null) {
                throw new IOException("Empty response body");
            }
            return objectMapper.readValue(body.string(), HealthCheck.class);
        }
    }

    private Response doRequest(String method, String path, Object body) throws IOException {
        Request.Builder requestBuilder = new Request.Builder()
                .url(baseUrl + path)
                .header("Authorization", "Bearer " + apiKey)
                .header("Content-Type", "application/json");

        if (body != null) {
            String json = objectMapper.writeValueAsString(body);
            requestBuilder.method(method, RequestBody.create(json, MediaType.parse("application/json")));
        } else if (method.equals("POST")) {
            requestBuilder.method(method, RequestBody.create("", MediaType.parse("application/json")));
        } else {
            requestBuilder.method(method, null);
        }

        Response response = httpClient.newCall(requestBuilder.build()).execute();

        if (!response.isSuccessful()) {
            handleError(response);
        }

        return response;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> parseResponse(Response response) throws IOException {
        ResponseBody body = response.body();
        if (body == null) {
            throw new IOException("Empty response body");
        }
        return objectMapper.readValue(body.string(), Map.class);
    }

    @SuppressWarnings("unchecked")
    private void handleError(Response response) throws IOException {
        String body = response.body() != null ? response.body().string() : "";
        Map<String, Object> errorData = new HashMap<>();
        try {
            errorData = objectMapper.readValue(body, Map.class);
        } catch (Exception ignored) {}

        String message = (String) errorData.getOrDefault("message", body);
        String workflowId = (String) errorData.get("workflow_id");

        switch (response.code()) {
            case 404 -> throw new WorkflowNotFoundException(workflowId);
            case 409 -> throw new WorkflowLockedException(workflowId);
            default -> throw new ContdException(message, workflowId);
        }
    }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private String apiKey;
        private String baseUrl = "https://api.contd.ai";
        private Duration timeout = Duration.ofSeconds(30);

        public Builder apiKey(String apiKey) {
            this.apiKey = apiKey;
            return this;
        }

        public Builder baseUrl(String baseUrl) {
            this.baseUrl = baseUrl;
            return this;
        }

        public Builder timeout(Duration timeout) {
            this.timeout = timeout;
            return this;
        }

        public ContdClient build() {
            if (apiKey == null || apiKey.isEmpty()) {
                throw new IllegalArgumentException("API key is required");
            }
            return new ContdClient(apiKey, baseUrl, timeout);
        }
    }
}

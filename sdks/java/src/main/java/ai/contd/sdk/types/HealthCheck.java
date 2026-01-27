package ai.contd.sdk.types;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.HashMap;
import java.util.Map;

/**
 * Health check response
 */
public class HealthCheck {
    @JsonProperty("status")
    private String status = "healthy";

    @JsonProperty("version")
    private String version;

    @JsonProperty("components")
    private Map<String, String> components = new HashMap<>();

    public HealthCheck() {}

    // Getters and setters
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getVersion() { return version; }
    public void setVersion(String version) { this.version = version; }
    public Map<String, String> getComponents() { return components; }
    public void setComponents(Map<String, String> components) { this.components = components; }
}

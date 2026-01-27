package ai.contd.sdk.types;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Rich metadata for workflow savepoints
 */
public class SavepointMetadata {
    @JsonProperty("goal_summary")
    private String goalSummary = "";

    @JsonProperty("hypotheses")
    private List<String> hypotheses = new ArrayList<>();

    @JsonProperty("questions")
    private List<String> questions = new ArrayList<>();

    @JsonProperty("decisions")
    private List<Map<String, Object>> decisions = new ArrayList<>();

    @JsonProperty("next_step")
    private String nextStep = "";

    public SavepointMetadata() {}

    // Getters and setters
    public String getGoalSummary() { return goalSummary; }
    public void setGoalSummary(String goalSummary) { this.goalSummary = goalSummary; }
    public List<String> getHypotheses() { return hypotheses; }
    public void setHypotheses(List<String> hypotheses) { this.hypotheses = hypotheses; }
    public List<String> getQuestions() { return questions; }
    public void setQuestions(List<String> questions) { this.questions = questions; }
    public List<Map<String, Object>> getDecisions() { return decisions; }
    public void setDecisions(List<Map<String, Object>> decisions) { this.decisions = decisions; }
    public String getNextStep() { return nextStep; }
    public void setNextStep(String nextStep) { this.nextStep = nextStep; }

    /**
     * Add a decision to the log
     */
    public void addDecision(String decision, String rationale, List<String> alternatives) {
        Map<String, Object> decisionEntry = new HashMap<>();
        decisionEntry.put("decision", decision);
        decisionEntry.put("rationale", rationale);
        decisionEntry.put("alternatives", alternatives != null ? alternatives : new ArrayList<>());
        decisions.add(decisionEntry);
    }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private final SavepointMetadata metadata = new SavepointMetadata();

        public Builder goalSummary(String goalSummary) {
            metadata.goalSummary = goalSummary;
            return this;
        }

        public Builder hypotheses(List<String> hypotheses) {
            metadata.hypotheses = hypotheses;
            return this;
        }

        public Builder addHypothesis(String hypothesis) {
            metadata.hypotheses.add(hypothesis);
            return this;
        }

        public Builder questions(List<String> questions) {
            metadata.questions = questions;
            return this;
        }

        public Builder addQuestion(String question) {
            metadata.questions.add(question);
            return this;
        }

        public Builder nextStep(String nextStep) {
            metadata.nextStep = nextStep;
            return this;
        }

        public SavepointMetadata build() {
            return metadata;
        }
    }
}

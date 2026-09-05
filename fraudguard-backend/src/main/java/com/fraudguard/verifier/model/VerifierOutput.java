package com.fraudguard.verifier.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.List;

/**
 * Strictly parsed and validated output from the LLM verifier.
 *
 * FAILS CLOSED: any parse error, missing field, invalid enum value, or out-of-range
 * confidence results in {@link #parseStrict(String)} throwing a {@link VerifierParseException}.
 * Callers MUST catch this and route the dispute to human review.
 * Never attempt to "fix up" malformed output and proceed — a model that didn't follow
 * the schema correctly is itself a signal not to trust its content.
 */
public class VerifierOutput {

    private static final ObjectMapper STRICT_MAPPER = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, true);

    @JsonProperty("verdict")
    private Verdict verdict;

    @JsonProperty("confidence")
    private Double confidence;

    @JsonProperty("contradiction_flags")
    private List<String> contradictionFlags;

    @JsonProperty("evidence_summary")
    private String evidenceSummary;

    /** Required by Jackson. */
    public VerifierOutput() {}

    /**
     * Parse and validate raw LLM JSON response.
     *
     * @param rawJson the full JSON string returned by the LLM
     * @return a validated VerifierOutput
     * @throws VerifierParseException if any field is missing, invalid, or out of range
     */
    public static VerifierOutput parseStrict(String rawJson) throws VerifierParseException {
        if (rawJson == null || rawJson.isBlank()) {
            throw new VerifierParseException("LLM returned empty response");
        }

        // Strip markdown code fences if the model wrapped the JSON anyway
        String cleaned = rawJson.strip();
        if (cleaned.startsWith("```")) {
            cleaned = cleaned.replaceAll("^```(?:json)?\\s*", "").replaceAll("\\s*```$", "").strip();
        }

        VerifierOutput out;
        try {
            out = STRICT_MAPPER.readValue(cleaned, VerifierOutput.class);
        } catch (Exception e) {
            throw new VerifierParseException("Failed to parse LLM JSON: " + e.getMessage(), e);
        }

        // Validate verdict
        if (out.verdict == null) {
            throw new VerifierParseException("Missing or unrecognized 'verdict' field");
        }

        // Validate confidence range
        if (out.confidence == null) {
            throw new VerifierParseException("Missing 'confidence' field");
        }
        if (out.confidence < 0.0 || out.confidence > 1.0) {
            throw new VerifierParseException(
                    "Confidence out of range [0.0, 1.0]: " + out.confidence);
        }

        // contradiction_flags must be present (can be empty list, but never null)
        if (out.contradictionFlags == null) {
            throw new VerifierParseException("Missing 'contradiction_flags' field");
        }

        // evidence_summary must be non-empty
        if (out.evidenceSummary == null || out.evidenceSummary.isBlank()) {
            throw new VerifierParseException("Missing or blank 'evidence_summary' field");
        }

        return out;
    }

    public Verdict getVerdict() { return verdict; }
    public void setVerdict(Verdict verdict) { this.verdict = verdict; }

    public Double getConfidence() { return confidence; }
    public void setConfidence(Double confidence) { this.confidence = confidence; }

    public List<String> getContradictionFlags() { return contradictionFlags; }
    public void setContradictionFlags(List<String> contradictionFlags) {
        this.contradictionFlags = contradictionFlags;
    }

    public String getEvidenceSummary() { return evidenceSummary; }
    public void setEvidenceSummary(String evidenceSummary) { this.evidenceSummary = evidenceSummary; }

    @Override
    public String toString() {
        return "VerifierOutput{verdict=" + verdict
                + ", confidence=" + confidence
                + ", contradictionFlags=" + contradictionFlags
                + ", evidenceSummary='" + evidenceSummary + "'}";
    }
}

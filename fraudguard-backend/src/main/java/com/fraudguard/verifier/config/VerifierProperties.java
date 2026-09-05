package com.fraudguard.verifier.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * Configuration properties for the LLM verifier, bound from {@code fraudguard.verifier.*}.
 */
@Configuration
@ConfigurationProperties(prefix = "fraudguard.verifier")
public class VerifierProperties {

    /** OpenAI model name, e.g. "gpt-4o". */
    private String model = "gpt-4o";

    /** HTTP timeout for LLM API calls in milliseconds. */
    private int timeoutMs = 15000;

    /**
     * Minimum confidence required, in combination with at least one contradiction flag,
     * to auto-resolve a dispute. Below this threshold, always routes to human review.
     */
    private double autoResolveConfidenceThreshold = 0.85;

    public String getModel() { return model; }
    public void setModel(String model) { this.model = model; }

    public int getTimeoutMs() { return timeoutMs; }
    public void setTimeoutMs(int timeoutMs) { this.timeoutMs = timeoutMs; }

    public double getAutoResolveConfidenceThreshold() { return autoResolveConfidenceThreshold; }
    public void setAutoResolveConfidenceThreshold(double t) { this.autoResolveConfidenceThreshold = t; }
}

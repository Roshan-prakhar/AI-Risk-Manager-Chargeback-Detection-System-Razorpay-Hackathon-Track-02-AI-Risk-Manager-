package com.fraudguard.verifier.model;

import com.fasterxml.jackson.annotation.JsonProperty;

/** The three possible verdicts the LLM verifier can produce. */
public enum Verdict {
    @JsonProperty("genuine_fraud")
    GENUINE_FRAUD,

    @JsonProperty("friendly_fraud")
    FRIENDLY_FRAUD,

    @JsonProperty("uncertain")
    UNCERTAIN
}

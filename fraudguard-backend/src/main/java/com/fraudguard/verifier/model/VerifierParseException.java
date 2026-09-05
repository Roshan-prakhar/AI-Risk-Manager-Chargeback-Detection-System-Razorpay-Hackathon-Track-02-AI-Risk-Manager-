package com.fraudguard.verifier.model;

/** Thrown when the LLM response cannot be strictly parsed. Callers MUST route to human review on this. */
public class VerifierParseException extends Exception {

    public VerifierParseException(String message) {
        super(message);
    }

    public VerifierParseException(String message, Throwable cause) {
        super(message, cause);
    }
}

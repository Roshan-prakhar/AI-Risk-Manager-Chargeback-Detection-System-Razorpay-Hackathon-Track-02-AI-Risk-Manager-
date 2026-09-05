package com.fraudguard.verifier.service;

/** Thrown when the LLM API call fails (network error, timeout, non-2xx HTTP status). */
public class LlmCallException extends Exception {

    public LlmCallException(String message) {
        super(message);
    }

    public LlmCallException(String message, Throwable cause) {
        super(message, cause);
    }
}

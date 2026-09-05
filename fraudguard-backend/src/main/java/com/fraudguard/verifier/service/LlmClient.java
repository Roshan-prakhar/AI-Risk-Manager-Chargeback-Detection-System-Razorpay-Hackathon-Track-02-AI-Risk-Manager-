package com.fraudguard.verifier.service;

/**
 * Abstraction over the LLM HTTP call. Allows the implementation to be swapped
 * (e.g., from OpenAI to Gemini) without touching the verifier service logic.
 */
public interface LlmClient {

    /**
     * Send a prompt and return the raw text response from the LLM.
     *
     * @param systemPrompt the filled, ready-to-send prompt
     * @return raw text from the model (expected to be a JSON string)
     * @throws LlmCallException if the API call fails, times out, or returns a non-2xx status
     */
    String call(String systemPrompt) throws LlmCallException;
}

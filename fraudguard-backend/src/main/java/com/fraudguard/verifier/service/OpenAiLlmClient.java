package com.fraudguard.verifier.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fraudguard.verifier.config.VerifierProperties;
import okhttp3.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * Calls the OpenAI Chat Completions API with JSON mode enabled.
 *
 * The API key is read from the {@code OPENAI_API_KEY} environment variable at runtime.
 * The app starts without it but will throw on the first actual LLM call if it's absent.
 *
 * JSON mode ({@code "response_format": {"type": "json_object"}}) is used to get a
 * schema-level guarantee from the API layer, stronger than prompt instructions alone.
 */
@Service
public class OpenAiLlmClient implements LlmClient {

    private static final Logger log = LoggerFactory.getLogger(OpenAiLlmClient.class);
    private static final String OPENAI_URL = "https://api.openai.com/v1/chat/completions";
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    private final OkHttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final VerifierProperties props;

    public OpenAiLlmClient(VerifierProperties props) {
        this.props = props;
        this.objectMapper = new ObjectMapper();
        this.httpClient = new OkHttpClient.Builder()
                .connectTimeout(5, TimeUnit.SECONDS)
                .readTimeout(props.getTimeoutMs(), TimeUnit.MILLISECONDS)
                .writeTimeout(10, TimeUnit.SECONDS)
                .build();
    }

    @Override
    public String call(String systemPrompt) throws LlmCallException {
        String apiKey = System.getenv("OPENAI_API_KEY");
        if (apiKey == null || apiKey.isBlank()) {
            throw new LlmCallException(
                    "OPENAI_API_KEY environment variable is not set. " +
                    "Set it before starting the application.");
        }

        String requestBody;
        try {
            requestBody = buildRequestBody(systemPrompt);
        } catch (Exception e) {
            throw new LlmCallException("Failed to build OpenAI request body: " + e.getMessage(), e);
        }

        Request request = new Request.Builder()
                .url(OPENAI_URL)
                .addHeader("Authorization", "Bearer " + apiKey)
                .addHeader("Content-Type", "application/json")
                .post(RequestBody.create(requestBody, JSON))
                .build();

        log.debug("Calling OpenAI {} with {} chars of prompt", props.getModel(), systemPrompt.length());

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                String errorBody = response.body() != null ? response.body().string() : "(no body)";
                throw new LlmCallException(
                        "OpenAI API returned HTTP " + response.code() + ": " + errorBody);
            }

            String responseBody = response.body() != null ? response.body().string() : "";
            return extractContent(responseBody);

        } catch (IOException e) {
            throw new LlmCallException("Network error calling OpenAI: " + e.getMessage(), e);
        }
    }

    private String buildRequestBody(String prompt) throws Exception {
        Map<String, Object> body = Map.of(
                "model", props.getModel(),
                "response_format", Map.of("type", "json_object"),
                "messages", List.of(
                        Map.of("role", "system", "content", prompt)
                ),
                "temperature", 0.0   // deterministic for verifier decisions
        );
        return objectMapper.writeValueAsString(body);
    }

    @SuppressWarnings("unchecked")
    private String extractContent(String responseBody) throws LlmCallException {
        try {
            Map<String, Object> root = objectMapper.readValue(responseBody, Map.class);
            List<Map<String, Object>> choices = (List<Map<String, Object>>) root.get("choices");
            if (choices == null || choices.isEmpty()) {
                throw new LlmCallException("OpenAI response has no choices: " + responseBody);
            }
            Map<String, Object> message = (Map<String, Object>) choices.get(0).get("message");
            if (message == null) {
                throw new LlmCallException("OpenAI choice has no message: " + responseBody);
            }
            Object content = message.get("content");
            if (content == null) {
                throw new LlmCallException("OpenAI message has null content");
            }
            return content.toString();
        } catch (LlmCallException e) {
            throw e;
        } catch (Exception e) {
            throw new LlmCallException("Failed to parse OpenAI response: " + e.getMessage(), e);
        }
    }
}

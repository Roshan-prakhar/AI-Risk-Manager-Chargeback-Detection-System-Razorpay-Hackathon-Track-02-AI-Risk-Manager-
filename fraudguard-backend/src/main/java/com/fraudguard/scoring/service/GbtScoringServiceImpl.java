package com.fraudguard.scoring.service;

import com.fraudguard.scoring.config.ScoringProperties;
import com.fraudguard.scoring.model.ScoringResult;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import java.time.Duration;
import java.util.Map;

@Service
public class GbtScoringServiceImpl implements GbtScoringService {

    private static final Logger log = LoggerFactory.getLogger(GbtScoringServiceImpl.class);
    private final WebClient webClient;
    private final ScoringProperties config;

    public GbtScoringServiceImpl(ScoringProperties config, WebClient.Builder webClientBuilder) {
        this.config = config;
        this.webClient = webClientBuilder.baseUrl(config.getPythonApiUrl()).build();
    }

    @Override
    public ScoringResult scoreTransaction(Map<String, Object> transactionFields) {
        try {
            return webClient.post()
                    .uri("/score")
                    .bodyValue(transactionFields)
                    .retrieve()
                    .bodyToMono(ScoringResult.class)
                    .timeout(Duration.ofMillis(config.getTimeoutMs()))
                    .block();
        } catch (Exception e) {
            log.error("Failed to score transaction", e);
            throw new RuntimeException("Failed to score transaction: " + e.getMessage(), e);
        }
    }
}

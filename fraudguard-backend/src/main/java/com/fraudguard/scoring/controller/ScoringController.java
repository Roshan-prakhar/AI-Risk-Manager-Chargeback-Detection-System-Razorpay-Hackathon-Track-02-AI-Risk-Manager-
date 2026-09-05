package com.fraudguard.scoring.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fraudguard.evidence.model.DeliveryStatus;
import com.fraudguard.evidence.model.EvidenceSnapshot;
import com.fraudguard.evidence.service.EvidenceCacheService;
import com.fraudguard.routing.config.TierThresholdConfig;
import com.fraudguard.routing.model.ScoredTransaction;
import com.fraudguard.routing.model.Tier;
import com.fraudguard.routing.model.TierAssignment;
import com.fraudguard.routing.repository.TierAssignmentRepository;
import com.fraudguard.routing.service.ThresholdRefreshService;
import com.fraudguard.routing.service.TierRouterService;
import com.fraudguard.scoring.model.ScoringResult;
import com.fraudguard.scoring.service.GbtScoringService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.time.Instant;

@RestController
@RequestMapping("/api/v1/transactions")
public class ScoringController {

    private final GbtScoringService gbtScoringService;
    private final TierRouterService tierRouterService;
    private final ThresholdRefreshService thresholdRefreshService;
    private final EvidenceCacheService evidenceCacheService;
    private final TierAssignmentRepository tierAssignmentRepository;
    private final ObjectMapper objectMapper;

    public ScoringController(GbtScoringService gbtScoringService,
                             TierRouterService tierRouterService,
                             ThresholdRefreshService thresholdRefreshService,
                             EvidenceCacheService evidenceCacheService,
                             TierAssignmentRepository tierAssignmentRepository,
                             ObjectMapper objectMapper) {
        this.gbtScoringService = gbtScoringService;
        this.tierRouterService = tierRouterService;
        this.thresholdRefreshService = thresholdRefreshService;
        this.evidenceCacheService = evidenceCacheService;
        this.tierAssignmentRepository = tierAssignmentRepository;
        this.objectMapper = objectMapper;
    }

    @PostMapping("/process")
    public ProcessingResponse processTransaction(@RequestBody Map<String, Object> transactionFields) {
        long transactionId = extractLong(transactionFields, "transactionId");
        double transactionAmt = extractDouble(transactionFields, "TransactionAmt");

        ScoringResult scoringResult = gbtScoringService.scoreTransaction(transactionFields);

        ScoredTransaction scoredTransaction = new ScoredTransaction();
        scoredTransaction.setTransactionId(transactionId);
        scoredTransaction.setGbtScore(scoringResult.getCalibratedProb());
        scoredTransaction.setTransactionAmount(transactionAmt);
        scoredTransaction.setFeatureSnapshot(transactionFields);

        TierThresholdConfig currentConfig = thresholdRefreshService.getCurrentConfig();

        TierAssignment tierAssignment = tierRouterService.assignTier(scoredTransaction, currentConfig);
        
        tierAssignmentRepository.save(tierAssignment);

        boolean evidenceCached = false;
        if (tierAssignment.getTier() == Tier.HIGH) {
            EvidenceSnapshot snapshot = new EvidenceSnapshot();
            snapshot.setTransactionId(transactionId);
            snapshot.setGbtScore(scoringResult.getCalibratedProb());
            snapshot.setTier(Tier.HIGH.name());
            snapshot.setCachedAt(Instant.now());
            snapshot.setDeliveryStatus(DeliveryStatus.PENDING);
            
            try {
                String featureSnapshotJson = objectMapper.writeValueAsString(transactionFields);
                snapshot.setFeatureSnapshotJson(featureSnapshotJson);
            } catch (JsonProcessingException e) {
                throw new RuntimeException("Failed to serialize features", e);
            }
            
            evidenceCacheService.cacheEvidence(snapshot);
            evidenceCached = true;
        }

        return new ProcessingResponse(scoringResult, tierAssignment, evidenceCached);
    }

    private long extractLong(Map<String, Object> map, String key) {
        Object val = map.get(key);
        if (val instanceof Number) {
            return ((Number) val).longValue();
        }
        if (val instanceof String) {
            return Long.parseLong((String) val);
        }
        throw new IllegalArgumentException("Missing or invalid " + key);
    }

    private double extractDouble(Map<String, Object> map, String key) {
        Object val = map.get(key);
        if (val instanceof Number) {
            return ((Number) val).doubleValue();
        }
        if (val instanceof String) {
            return Double.parseDouble((String) val);
        }
        throw new IllegalArgumentException("Missing or invalid " + key);
    }

    public static class ProcessingResponse {
        private ScoringResult scoringResult;
        private TierAssignment tierAssignment;
        private boolean evidenceCached;

        public ProcessingResponse(ScoringResult scoringResult, TierAssignment tierAssignment, boolean evidenceCached) {
            this.scoringResult = scoringResult;
            this.tierAssignment = tierAssignment;
            this.evidenceCached = evidenceCached;
        }

        public ScoringResult getScoringResult() { return scoringResult; }
        public void setScoringResult(ScoringResult scoringResult) { this.scoringResult = scoringResult; }

        public TierAssignment getTierAssignment() { return tierAssignment; }
        public void setTierAssignment(TierAssignment tierAssignment) { this.tierAssignment = tierAssignment; }

        public boolean isEvidenceCached() { return evidenceCached; }
        public void setEvidenceCached(boolean evidenceCached) { this.evidenceCached = evidenceCached; }
    }
}

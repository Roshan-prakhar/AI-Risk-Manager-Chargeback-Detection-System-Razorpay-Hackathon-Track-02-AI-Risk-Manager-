package com.fraudguard.evidence.controller;

import com.fraudguard.evidence.model.EvidenceSnapshot;
import com.fraudguard.evidence.service.DeliveryWebhookHandler;
import com.fraudguard.evidence.service.EvidenceCacheService;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import java.time.Instant;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/evidence")
@RequiredArgsConstructor
public class EvidenceController {

    private final EvidenceCacheService evidenceCacheService;
    private final DeliveryWebhookHandler deliveryWebhookHandler;

    @GetMapping("/{transactionId}")
    public ResponseEntity<EvidenceSnapshot> getEvidence(@PathVariable long transactionId) {
        Optional<EvidenceSnapshot> snapshotOpt = evidenceCacheService.retrieveEvidence(transactionId);
        return snapshotOpt.map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping("/delivery")
    public ResponseEntity<Void> deliveryConfirmed(@RequestBody DeliveryConfirmationRequest request) {
        deliveryWebhookHandler.onDeliveryConfirmed(request.getTransactionId(), request.getConfirmedAt());
        return ResponseEntity.ok().build();
    }
    
    @Data
    public static class DeliveryConfirmationRequest {
        private long transactionId;
        private Instant confirmedAt;
    }
}

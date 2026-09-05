package com.fraudguard.evidence.service;

import com.fraudguard.evidence.model.DeliveryStatus;
import com.fraudguard.evidence.model.EvidenceSnapshot;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import java.time.Instant;
import java.util.Optional;

@Service
@RequiredArgsConstructor
@Slf4j
public class DeliveryWebhookHandlerImpl implements DeliveryWebhookHandler {

    private final ColdStore coldStore;
    private final HotCacheStore hotCacheStore;

    @Override
    public void onDeliveryConfirmed(long transactionId, Instant confirmedAt) {
        Optional<EvidenceSnapshot> coldSnapshotOpt = coldStore.get(transactionId);
        if (coldSnapshotOpt.isEmpty()) {
            log.warn("Received delivery confirmation for unknown transactionId: {}", transactionId);
            return;
        }
        
        EvidenceSnapshot snapshot = coldSnapshotOpt.get();
        snapshot.setDeliveryStatus(DeliveryStatus.CONFIRMED);
        snapshot.setDeliveryConfirmedAt(confirmedAt);
        
        coldStore.put(transactionId, snapshot);
        hotCacheStore.update(transactionId, snapshot);
        
        log.info("Delivery confirmed for transactionId: {}", transactionId);
    }
}

package com.fraudguard.evidence.service;

import com.fraudguard.evidence.model.EvidenceSnapshot;
import java.time.Duration;
import java.util.Optional;

public interface HotCacheStore {
    void put(long transactionId, EvidenceSnapshot snapshot, Duration ttl);
    Optional<EvidenceSnapshot> get(long transactionId);
    void update(long transactionId, EvidenceSnapshot snapshot);
}

package com.fraudguard.evidence.service;

import com.fraudguard.evidence.model.EvidenceSnapshot;
import java.time.Duration;
import java.util.Optional;

public interface ColdStore {
    void put(long transactionId, EvidenceSnapshot snapshot);
    Optional<EvidenceSnapshot> get(long transactionId);
    void purgeOlderThan(Duration retention);
}

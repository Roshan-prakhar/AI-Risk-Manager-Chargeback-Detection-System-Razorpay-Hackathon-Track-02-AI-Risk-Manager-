package com.fraudguard.evidence.service;

import com.fraudguard.evidence.model.EvidenceSnapshot;
import java.util.Optional;

public interface EvidenceCacheService {
    void cacheEvidence(EvidenceSnapshot snapshot);
    Optional<EvidenceSnapshot> retrieveEvidence(long transactionId);
}

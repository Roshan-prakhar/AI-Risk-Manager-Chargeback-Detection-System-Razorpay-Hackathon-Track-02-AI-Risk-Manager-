package com.fraudguard.evidence.service;

import com.fraudguard.evidence.model.EvidenceSnapshot;
import com.fraudguard.evidence.repository.EvidenceSnapshotRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

@Service("coldStore")
@RequiredArgsConstructor
@Slf4j
public class PostgresColdStore implements ColdStore {

    private final EvidenceSnapshotRepository repository;

    @Override
    @Transactional
    public void put(long transactionId, EvidenceSnapshot snapshot) {
        repository.save(snapshot);
    }

    @Override
    public Optional<EvidenceSnapshot> get(long transactionId) {
        return repository.findById(transactionId);
    }

    @Override
    @Transactional
    public void purgeOlderThan(Duration retention) {
        Instant cutoff = Instant.now().minus(retention);
        repository.deleteByCachedAtBefore(cutoff);
        log.info("Purged older evidence snapshots from before {}", cutoff);
    }
}

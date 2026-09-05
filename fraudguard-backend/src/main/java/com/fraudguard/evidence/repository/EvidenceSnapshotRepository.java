package com.fraudguard.evidence.repository;

import com.fraudguard.evidence.model.EvidenceSnapshot;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.time.Instant;

@Repository
public interface EvidenceSnapshotRepository extends JpaRepository<EvidenceSnapshot, Long> {
    void deleteByCachedAtBefore(Instant cutoff);
}

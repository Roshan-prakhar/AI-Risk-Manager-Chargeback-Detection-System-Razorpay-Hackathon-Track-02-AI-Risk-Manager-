package com.fraudguard.evidence.service;

import com.fraudguard.evidence.config.EvidenceProperties;
import com.fraudguard.evidence.model.EvidenceSnapshot;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import java.time.Duration;
import java.util.Optional;

@Service
@RequiredArgsConstructor
@Slf4j
public class EvidenceCacheServiceImpl implements EvidenceCacheService {

    private final HotCacheStore hotCacheStore;
    private final ColdStore coldStore;
    private final EvidenceProperties properties;

    @Override
    public void cacheEvidence(EvidenceSnapshot snapshot) {
        Duration ttl = Duration.ofDays(properties.getHotCacheTtlDays());
        hotCacheStore.put(snapshot.getTransactionId(), snapshot, ttl);
        coldStore.put(snapshot.getTransactionId(), snapshot);
    }

    @Override
    public Optional<EvidenceSnapshot> retrieveEvidence(long transactionId) {
        Optional<EvidenceSnapshot> hotSnapshot = hotCacheStore.get(transactionId);
        if (hotSnapshot.isPresent()) {
            return hotSnapshot;
        }
        return coldStore.get(transactionId);
    }

    @Scheduled(cron = "#{@evidenceProperties.purgeCron}")
    public void purgeColdStore() {
        log.info("Running cold store purge job");
        coldStore.purgeOlderThan(Duration.ofDays(properties.getColdRetentionDays()));
    }
}

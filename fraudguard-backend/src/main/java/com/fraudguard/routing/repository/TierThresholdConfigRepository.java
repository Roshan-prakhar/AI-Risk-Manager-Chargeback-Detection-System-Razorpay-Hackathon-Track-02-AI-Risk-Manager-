package com.fraudguard.routing.repository;

import com.fraudguard.routing.config.TierThresholdConfig;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.Optional;

@Repository
public interface TierThresholdConfigRepository extends JpaRepository<TierThresholdConfig, Long> {
    Optional<TierThresholdConfig> findTopByOrderByComputedAtDesc();
}

package com.fraudguard.routing.service;

import com.fraudguard.routing.config.RoutingProperties;
import com.fraudguard.routing.config.TierThresholdConfig;
import com.fraudguard.routing.repository.TierThresholdConfigRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

@Service
public class ThresholdRefreshServiceImpl implements ThresholdRefreshService {

    private static final Logger log = LoggerFactory.getLogger(ThresholdRefreshServiceImpl.class);

    private final TierThresholdConfigRepository repository;
    private final RoutingProperties properties;

    private volatile TierThresholdConfig currentConfig;

    @Autowired
    public ThresholdRefreshServiceImpl(TierThresholdConfigRepository repository, RoutingProperties properties) {
        this.repository = repository;
        this.properties = properties;
    }

    @Override
    public TierThresholdConfig getCurrentConfig() {
        if (currentConfig == null) {
            refreshThresholds();
        }
        return currentConfig;
    }

    @Override
    @Scheduled(cron = "${fraudguard.routing.refresh-cron}")
    public void refreshThresholds() {
        Optional<TierThresholdConfig> latestConfig = repository.findTopByOrderByComputedAtDesc();
        if (latestConfig.isPresent()) {
            TierThresholdConfig config = latestConfig.get();
            this.currentConfig = config;
            log.info("Refreshed threshold config, latest id: {}", config.getId());
            
            if (isConfigStale(config, Duration.ofHours(properties.getStalenessMaxHours()))) {
                log.warn("Threshold config is stale. Computed at: {}, max age hours: {}", config.getComputedAt(), properties.getStalenessMaxHours());
            }
        } else {
            log.warn("No tier threshold config found in database.");
        }
    }

    @Override
    public boolean isConfigStale(TierThresholdConfig config, Duration maxAge) {
        if (config == null || config.getComputedAt() == null) {
            return true;
        }
        return config.getComputedAt().isBefore(Instant.now().minus(maxAge));
    }
}

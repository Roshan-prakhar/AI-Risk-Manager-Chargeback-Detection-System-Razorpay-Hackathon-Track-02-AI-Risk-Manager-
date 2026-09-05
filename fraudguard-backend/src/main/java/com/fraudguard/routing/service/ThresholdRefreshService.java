package com.fraudguard.routing.service;

import com.fraudguard.routing.config.TierThresholdConfig;
import java.time.Duration;

public interface ThresholdRefreshService {
    TierThresholdConfig getCurrentConfig();
    void refreshThresholds();
    boolean isConfigStale(TierThresholdConfig config, Duration maxAge);
}

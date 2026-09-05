package com.fraudguard.routing.service;

import com.fraudguard.routing.config.TierThresholdConfig;
import com.fraudguard.routing.model.ScoredTransaction;
import com.fraudguard.routing.model.TierAssignment;
import java.util.List;

public interface TierRouterService {
    TierAssignment assignTier(ScoredTransaction tx, TierThresholdConfig config);
    List<TierAssignment> assignTierBatch(List<ScoredTransaction> txs, TierThresholdConfig config);
}

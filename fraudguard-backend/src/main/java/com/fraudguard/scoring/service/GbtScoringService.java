package com.fraudguard.scoring.service;

import com.fraudguard.scoring.model.ScoringResult;
import java.util.Map;

public interface GbtScoringService {
    ScoringResult scoreTransaction(Map<String, Object> transactionFields);
}

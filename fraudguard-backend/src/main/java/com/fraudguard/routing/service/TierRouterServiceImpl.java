package com.fraudguard.routing.service;

import com.fraudguard.routing.config.TierThresholdConfig;
import com.fraudguard.routing.model.EscalationReason;
import com.fraudguard.routing.model.ScoredTransaction;
import com.fraudguard.routing.model.Tier;
import com.fraudguard.routing.model.TierAssignment;
import com.fraudguard.routing.repository.TierAssignmentRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

@Service
public class TierRouterServiceImpl implements TierRouterService {

    private final TierAssignmentRepository repository;

    @Autowired
    public TierRouterServiceImpl(TierAssignmentRepository repository) {
        this.repository = repository;
    }

    @Override
    public TierAssignment assignTier(ScoredTransaction tx, TierThresholdConfig config) {
        boolean scoreAboveHigh = tx.getGbtScore() >= config.getModerateMaxScore();
        boolean valueAboveHigh = tx.getTransactionAmount() >= config.getValueThreshold();
        
        Tier tier;
        EscalationReason reason = null;
        
        if (scoreAboveHigh && valueAboveHigh) {
            tier = Tier.HIGH;
            reason = EscalationReason.BOTH;
        } else if (scoreAboveHigh) {
            tier = Tier.HIGH;
            reason = EscalationReason.SCORE;
        } else if (valueAboveHigh) {
            tier = Tier.HIGH;
            reason = EscalationReason.VALUE;
        } else if (tx.getGbtScore() >= config.getTrivialMaxScore()) {
            tier = Tier.MODERATE;
        } else {
            tier = Tier.TRIVIAL;
        }
        
        TierAssignment assignment = new TierAssignment();
        assignment.setTransactionId(tx.getTransactionId());
        assignment.setGbtScore(tx.getGbtScore());
        assignment.setTransactionAmount(tx.getTransactionAmount());
        assignment.setTier(tier);
        assignment.setEscalationReason(reason);
        assignment.setThresholdConfigId(config.getId());
        assignment.setAssignedAt(Instant.now());
        
        return assignment;
    }

    @Override
    public List<TierAssignment> assignTierBatch(List<ScoredTransaction> txs, TierThresholdConfig config) {
        List<TierAssignment> assignments = new ArrayList<>();
        for (ScoredTransaction tx : txs) {
            assignments.add(assignTier(tx, config));
        }
        return repository.saveAll(assignments);
    }

    public TierAssignment save(TierAssignment assignment) {
        return repository.save(assignment);
    }
}

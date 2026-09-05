package com.fraudguard.routing.model;

import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "tier_assignments")
public class TierAssignment {

    @Id
    private Long transactionId;

    private double gbtScore;
    private double transactionAmount;

    @Enumerated(EnumType.STRING)
    private Tier tier;

    @Enumerated(EnumType.STRING)
    private EscalationReason escalationReason;

    private Long thresholdConfigId;

    private Instant assignedAt;

    @PrePersist
    public void prePersist() {
        if (assignedAt == null) {
            assignedAt = Instant.now();
        }
    }

    public Long getTransactionId() {
        return transactionId;
    }

    public void setTransactionId(Long transactionId) {
        this.transactionId = transactionId;
    }

    public double getGbtScore() {
        return gbtScore;
    }

    public void setGbtScore(double gbtScore) {
        this.gbtScore = gbtScore;
    }

    public double getTransactionAmount() {
        return transactionAmount;
    }

    public void setTransactionAmount(double transactionAmount) {
        this.transactionAmount = transactionAmount;
    }

    public Tier getTier() {
        return tier;
    }

    public void setTier(Tier tier) {
        this.tier = tier;
    }

    public EscalationReason getEscalationReason() {
        return escalationReason;
    }

    public void setEscalationReason(EscalationReason escalationReason) {
        this.escalationReason = escalationReason;
    }

    public Long getThresholdConfigId() {
        return thresholdConfigId;
    }

    public void setThresholdConfigId(Long thresholdConfigId) {
        this.thresholdConfigId = thresholdConfigId;
    }

    public Instant getAssignedAt() {
        return assignedAt;
    }

    public void setAssignedAt(Instant assignedAt) {
        this.assignedAt = assignedAt;
    }
}

package com.fraudguard.routing.config;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "tier_threshold_config")
public class TierThresholdConfig {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private double trivialMaxScore;
    private double moderateMaxScore;
    private double valueThreshold;
    private Instant computedAt;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public double getTrivialMaxScore() {
        return trivialMaxScore;
    }

    public void setTrivialMaxScore(double trivialMaxScore) {
        this.trivialMaxScore = trivialMaxScore;
    }

    public double getModerateMaxScore() {
        return moderateMaxScore;
    }

    public void setModerateMaxScore(double moderateMaxScore) {
        this.moderateMaxScore = moderateMaxScore;
    }

    public double getValueThreshold() {
        return valueThreshold;
    }

    public void setValueThreshold(double valueThreshold) {
        this.valueThreshold = valueThreshold;
    }

    public Instant getComputedAt() {
        return computedAt;
    }

    public void setComputedAt(Instant computedAt) {
        this.computedAt = computedAt;
    }
}

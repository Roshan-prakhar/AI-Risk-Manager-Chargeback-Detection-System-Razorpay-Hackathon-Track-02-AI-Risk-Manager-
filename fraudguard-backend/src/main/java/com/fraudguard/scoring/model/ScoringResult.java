package com.fraudguard.scoring.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public class ScoringResult {

    @JsonProperty("raw_prob")
    private double rawProb;

    @JsonProperty("calibrated_prob")
    private double calibratedProb;

    private int decision;
    private double threshold;

    public ScoringResult() {
    }

    public double getRawProb() {
        return rawProb;
    }

    public void setRawProb(double rawProb) {
        this.rawProb = rawProb;
    }

    public double getCalibratedProb() {
        return calibratedProb;
    }

    public void setCalibratedProb(double calibratedProb) {
        this.calibratedProb = calibratedProb;
    }

    public int getDecision() {
        return decision;
    }

    public void setDecision(int decision) {
        this.decision = decision;
    }

    public double getThreshold() {
        return threshold;
    }

    public void setThreshold(double threshold) {
        this.threshold = threshold;
    }
}

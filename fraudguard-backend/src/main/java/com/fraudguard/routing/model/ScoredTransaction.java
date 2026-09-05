package com.fraudguard.routing.model;

import java.util.Map;

public class ScoredTransaction {
    private long transactionId;
    private double gbtScore;
    private double transactionAmount;
    private Map<String, Object> featureSnapshot;

    public ScoredTransaction() {}

    public ScoredTransaction(long transactionId, double gbtScore, double transactionAmount, Map<String, Object> featureSnapshot) {
        this.transactionId = transactionId;
        this.gbtScore = gbtScore;
        this.transactionAmount = transactionAmount;
        this.featureSnapshot = featureSnapshot;
    }

    public long getTransactionId() {
        return transactionId;
    }

    public void setTransactionId(long transactionId) {
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

    public Map<String, Object> getFeatureSnapshot() {
        return featureSnapshot;
    }

    public void setFeatureSnapshot(Map<String, Object> featureSnapshot) {
        this.featureSnapshot = featureSnapshot;
    }
}

package com.fraudguard.verifier.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;

import java.time.Instant;

/**
 * Persisted record of a dispute verdict, including the LLM's reasoning and routing outcome.
 * Stored in the {@code dispute_verdicts} table for audit and human-review queues.
 */
@Entity
@Table(name = "dispute_verdicts")
public class DisputeVerdict {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private Long transactionId;

    @Enumerated(EnumType.STRING)
    private ReasonCode reasonCode;

    @Enumerated(EnumType.STRING)
    private Verdict verdict;

    private Double confidence;

    /** Pipe-delimited list of contradiction flag strings. */
    @Column(columnDefinition = "CLOB")
    private String contradictionFlags;

    @Column(length = 1000)
    private String evidenceSummary;

    @Enumerated(EnumType.STRING)
    private RoutingDecision routingDecision;

    @Column(columnDefinition = "CLOB")
    private String customerText;

    private Instant decidedAt;

    @PrePersist
    public void prePersist() {
        if (decidedAt == null) decidedAt = Instant.now();
    }

    public DisputeVerdict() {}

    // Getters and setters

    public Long getId() { return id; }

    public Long getTransactionId() { return transactionId; }
    public void setTransactionId(Long transactionId) { this.transactionId = transactionId; }

    public ReasonCode getReasonCode() { return reasonCode; }
    public void setReasonCode(ReasonCode reasonCode) { this.reasonCode = reasonCode; }

    public Verdict getVerdict() { return verdict; }
    public void setVerdict(Verdict verdict) { this.verdict = verdict; }

    public Double getConfidence() { return confidence; }
    public void setConfidence(Double confidence) { this.confidence = confidence; }

    public String getContradictionFlags() { return contradictionFlags; }
    public void setContradictionFlags(String contradictionFlags) {
        this.contradictionFlags = contradictionFlags;
    }

    public String getEvidenceSummary() { return evidenceSummary; }
    public void setEvidenceSummary(String evidenceSummary) { this.evidenceSummary = evidenceSummary; }

    public RoutingDecision getRoutingDecision() { return routingDecision; }
    public void setRoutingDecision(RoutingDecision routingDecision) {
        this.routingDecision = routingDecision;
    }

    public String getCustomerText() { return customerText; }
    public void setCustomerText(String customerText) { this.customerText = customerText; }

    public Instant getDecidedAt() { return decidedAt; }
    public void setDecidedAt(Instant decidedAt) { this.decidedAt = decidedAt; }
}

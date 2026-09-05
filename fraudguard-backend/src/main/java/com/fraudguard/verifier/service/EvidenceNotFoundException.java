package com.fraudguard.verifier.service;

/** Thrown when a dispute is submitted for a transaction that has no cached evidence snapshot. */
public class EvidenceNotFoundException extends RuntimeException {
    public EvidenceNotFoundException(long transactionId) {
        super("No evidence snapshot found for transactionId=" + transactionId
                + ". The transaction may not have been routed to HIGH tier, "
                + "or its evidence may have expired from the hot cache.");
    }
}

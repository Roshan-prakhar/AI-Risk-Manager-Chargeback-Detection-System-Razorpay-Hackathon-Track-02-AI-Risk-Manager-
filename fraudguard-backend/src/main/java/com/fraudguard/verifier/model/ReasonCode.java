package com.fraudguard.verifier.model;

/**
 * Supported dispute reason codes.
 * Any reason code NOT in this enum is rejected at the service layer
 * before it ever reaches the LLM.
 */
public enum ReasonCode {
    UNAUTHORIZED_TRANSACTION,
    ITEM_NOT_RECEIVED
}

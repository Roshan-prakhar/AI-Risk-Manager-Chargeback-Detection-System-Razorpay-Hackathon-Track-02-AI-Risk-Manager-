package com.fraudguard.verifier.service;

/** Thrown when a dispute is submitted with a reason code not supported by the verifier. */
public class UnsupportedReasonCodeException extends RuntimeException {
    public UnsupportedReasonCodeException(String reasonCode) {
        super("Reason code '" + reasonCode
                + "' is not supported by the LLM verifier. "
                + "Supported codes: UNAUTHORIZED_TRANSACTION, ITEM_NOT_RECEIVED.");
    }
}

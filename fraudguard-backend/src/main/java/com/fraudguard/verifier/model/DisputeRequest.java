package com.fraudguard.verifier.model;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/**
 * Inbound dispute submission from a customer or payment processor.
 * reasonCode is validated against the ReasonCode enum at the controller layer;
 * any unsupported value returns 400 before reaching the LLM.
 */
public class DisputeRequest {

    @NotNull
    private Long transactionId;

    @NotNull
    private ReasonCode reasonCode;

    /** Raw, untrusted text from the customer. Treated as DATA, not instructions. */
    @NotBlank
    private String customerText;

    public DisputeRequest() {}

    public DisputeRequest(Long transactionId, ReasonCode reasonCode, String customerText) {
        this.transactionId = transactionId;
        this.reasonCode = reasonCode;
        this.customerText = customerText;
    }

    public Long getTransactionId() { return transactionId; }
    public void setTransactionId(Long transactionId) { this.transactionId = transactionId; }

    public ReasonCode getReasonCode() { return reasonCode; }
    public void setReasonCode(ReasonCode reasonCode) { this.reasonCode = reasonCode; }

    public String getCustomerText() { return customerText; }
    public void setCustomerText(String customerText) { this.customerText = customerText; }
}

package com.fraudguard.evidence.service;

import java.time.Instant;

public interface DeliveryWebhookHandler {
    void onDeliveryConfirmed(long transactionId, Instant confirmedAt);
}

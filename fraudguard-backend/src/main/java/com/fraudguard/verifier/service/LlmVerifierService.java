package com.fraudguard.verifier.service;

import com.fraudguard.verifier.model.DisputeRequest;
import com.fraudguard.verifier.model.DisputeVerdict;

/**
 * Entry point for Stage 4 LLM verification.
 * Implementations orchestrate evidence fetch → prompt fill → LLM call → parse → route → persist.
 */
public interface LlmVerifierService {

    /**
     * Verify a dispute and return a persisted verdict including routing decision.
     *
     * @param request the inbound dispute (reason code + customer text)
     * @return persisted DisputeVerdict
     * @throws UnsupportedReasonCodeException if the reason code is not UNAUTHORIZED_TRANSACTION
     *         or ITEM_NOT_RECEIVED — rejected BEFORE reaching the LLM
     * @throws EvidenceNotFoundException if no cached evidence exists for the transaction —
     *         caller should prompt the customer to wait for evidence to be indexed
     */
    DisputeVerdict verify(DisputeRequest request);
}

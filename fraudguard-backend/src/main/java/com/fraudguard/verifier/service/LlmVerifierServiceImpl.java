package com.fraudguard.verifier.service;

import com.fraudguard.evidence.model.EvidenceSnapshot;
import com.fraudguard.evidence.service.EvidenceCacheService;
import com.fraudguard.verifier.model.*;
import com.fraudguard.verifier.repository.DisputeVerdictRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * Core Stage 4 orchestrator. Enforces the full trust boundary:
 *
 * <pre>
 *   DisputeRequest (inbound)
 *     → reason code gate (rejects unsupported codes before LLM)
 *     → evidence fetch from Stage 3 cache (hot then cold)
 *     → prompt build (PromptBuilder — LLM sees only what we hand it)
 *     → LLM call (OpenAiLlmClient)
 *     → strict parse (VerifierOutput.parseStrict — fails closed on malformed output)
 *     → route (VerdictRouter — UNCERTAIN + parse failures → HUMAN_REVIEW)
 *     → persist (DisputeVerdictRepository)
 *     → return DisputeVerdict
 * </pre>
 */
@Service
public class LlmVerifierServiceImpl implements LlmVerifierService {

    private static final Logger log = LoggerFactory.getLogger(LlmVerifierServiceImpl.class);

    private final EvidenceCacheService evidenceCacheService;
    private final PromptBuilder promptBuilder;
    private final LlmClient llmClient;
    private final VerdictRouter verdictRouter;
    private final DisputeVerdictRepository verdictRepository;

    public LlmVerifierServiceImpl(EvidenceCacheService evidenceCacheService,
                                  PromptBuilder promptBuilder,
                                  LlmClient llmClient,
                                  VerdictRouter verdictRouter,
                                  DisputeVerdictRepository verdictRepository) {
        this.evidenceCacheService = evidenceCacheService;
        this.promptBuilder = promptBuilder;
        this.llmClient = llmClient;
        this.verdictRouter = verdictRouter;
        this.verdictRepository = verdictRepository;
    }

    @Override
    public DisputeVerdict verify(DisputeRequest request) {

        // ── 1. Reason code gate ─────────────────────────────────────────────────
        // ReasonCode is already an enum on DisputeRequest; if it's null here it means
        // an unmapped string was submitted. The controller catches deserialization errors,
        // but belt-and-suspenders check here as well.
        if (request.getReasonCode() == null) {
            throw new UnsupportedReasonCodeException("null");
        }

        long txId = request.getTransactionId();
        log.info("Verifying dispute: txId={}, reasonCode={}", txId, request.getReasonCode());

        // ── 2. Evidence fetch ────────────────────────────────────────────────────
        Optional<EvidenceSnapshot> evidenceOpt = evidenceCacheService.retrieveEvidence(txId);
        if (evidenceOpt.isEmpty()) {
            throw new EvidenceNotFoundException(txId);
        }
        EvidenceSnapshot evidence = evidenceOpt.get();

        // ── 3. Prompt build ──────────────────────────────────────────────────────
        String prompt = promptBuilder.build(request.getReasonCode(), evidence, request.getCustomerText());
        log.debug("Built prompt ({} chars) for txId={}", prompt.length(), txId);

        // ── 4. LLM call + strict parse ────────────────────────────────────────────
        VerifierOutput verifierOutput;
        RoutingDecision routingDecision;
        try {
            String rawLlmResponse = llmClient.call(prompt);
            log.debug("Raw LLM response for txId={}: {}", txId, rawLlmResponse);
            verifierOutput = VerifierOutput.parseStrict(rawLlmResponse);
        } catch (VerifierParseException e) {
            // Malformed output: FAIL CLOSED → human review, persist with UNCERTAIN verdict
            log.warn("LLM parse failure for txId={}: {} — routing to HUMAN_REVIEW", txId, e.getMessage());
            return persistVerdict(request, Verdict.UNCERTAIN, 0.0,
                    List.of("PARSE_FAILURE: " + e.getMessage()), "LLM output could not be parsed.",
                    RoutingDecision.HUMAN_REVIEW);
        } catch (LlmCallException e) {
            // Transport failure: FAIL CLOSED → human review
            log.error("LLM call failed for txId={}: {}", txId, e.getMessage());
            return persistVerdict(request, Verdict.UNCERTAIN, 0.0,
                    List.of("LLM_CALL_FAILURE: " + e.getMessage()), "LLM service unavailable.",
                    RoutingDecision.HUMAN_REVIEW);
        }

        // ── 5. Route ─────────────────────────────────────────────────────────────
        routingDecision = verdictRouter.route(verifierOutput);

        // ── 6. Persist and return ─────────────────────────────────────────────────
        DisputeVerdict verdict = persistVerdict(request,
                verifierOutput.getVerdict(),
                verifierOutput.getConfidence(),
                verifierOutput.getContradictionFlags(),
                verifierOutput.getEvidenceSummary(),
                routingDecision);

        log.info("Verdict for txId={}: {} (confidence={}) → {}",
                txId, verdict.getVerdict(), verdict.getConfidence(), verdict.getRoutingDecision());
        return verdict;
    }

    private DisputeVerdict persistVerdict(DisputeRequest request,
                                          Verdict verdict,
                                          double confidence,
                                          List<String> flags,
                                          String summary,
                                          RoutingDecision decision) {
        DisputeVerdict dv = new DisputeVerdict();
        dv.setTransactionId(request.getTransactionId());
        dv.setReasonCode(request.getReasonCode());
        dv.setVerdict(verdict);
        dv.setConfidence(confidence);
        // Store flags as pipe-delimited string (CLOB column)
        dv.setContradictionFlags(flags != null ? String.join("|", flags) : "");
        dv.setEvidenceSummary(summary);
        dv.setRoutingDecision(decision);
        dv.setCustomerText(request.getCustomerText());
        return verdictRepository.save(dv);
    }
}

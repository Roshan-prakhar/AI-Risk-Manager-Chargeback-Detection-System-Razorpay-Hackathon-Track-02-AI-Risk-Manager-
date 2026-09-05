package com.fraudguard.verifier.controller;

import com.fraudguard.verifier.model.DisputeRequest;
import com.fraudguard.verifier.model.DisputeVerdict;
import com.fraudguard.verifier.model.RoutingDecision;
import com.fraudguard.verifier.repository.DisputeVerdictRepository;
import com.fraudguard.verifier.service.EvidenceNotFoundException;
import com.fraudguard.verifier.service.LlmVerifierService;
import com.fraudguard.verifier.service.UnsupportedReasonCodeException;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * REST controller for Stage 4 LLM dispute verification.
 *
 * Endpoints:
 *   POST /api/v1/disputes/verify        — submit a dispute for LLM verification
 *   GET  /api/v1/disputes/{txId}        — retrieve all verdicts for a transaction
 *   GET  /api/v1/disputes/review-queue  — list all verdicts routed to HUMAN_REVIEW
 */
@RestController
@RequestMapping("/api/v1/disputes")
public class DisputeController {

    private static final Logger log = LoggerFactory.getLogger(DisputeController.class);

    private final LlmVerifierService verifierService;
    private final DisputeVerdictRepository verdictRepository;

    public DisputeController(LlmVerifierService verifierService,
                             DisputeVerdictRepository verdictRepository) {
        this.verifierService = verifierService;
        this.verdictRepository = verdictRepository;
    }

    /**
     * Submit a dispute for LLM verification.
     * The reasonCode field must be UNAUTHORIZED_TRANSACTION or ITEM_NOT_RECEIVED.
     * Any other value returns 400 immediately.
     */
    @PostMapping("/verify")
    public ResponseEntity<?> verify(@Valid @RequestBody DisputeRequest request) {
        try {
            DisputeVerdict verdict = verifierService.verify(request);
            return ResponseEntity.ok(verdict);

        } catch (UnsupportedReasonCodeException e) {
            log.warn("Rejected unsupported reason code: {}", e.getMessage());
            return ResponseEntity.badRequest()
                    .body(Map.of("error", e.getMessage(), "code", "UNSUPPORTED_REASON_CODE"));

        } catch (EvidenceNotFoundException e) {
            log.warn("Evidence not found: {}", e.getMessage());
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", e.getMessage(), "code", "EVIDENCE_NOT_FOUND"));

        } catch (Exception e) {
            log.error("Unexpected error during dispute verification", e);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(Map.of("error", "Internal server error", "code", "INTERNAL_ERROR"));
        }
    }

    /** Retrieve all verdicts for a given transaction ID. */
    @GetMapping("/{transactionId}")
    public ResponseEntity<?> getVerdicts(@PathVariable Long transactionId) {
        List<DisputeVerdict> verdicts = verdictRepository.findByTransactionId(transactionId);
        if (verdicts.isEmpty()) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error", "No verdicts found for transactionId=" + transactionId));
        }
        return ResponseEntity.ok(verdicts);
    }

    /**
     * List all disputes routed to HUMAN_REVIEW.
     * This is the human-review queue for analysts.
     */
    @GetMapping("/review-queue")
    public ResponseEntity<List<DisputeVerdict>> reviewQueue() {
        List<DisputeVerdict> queue = verdictRepository.findAll().stream()
                .filter(v -> v.getRoutingDecision() == RoutingDecision.HUMAN_REVIEW)
                .toList();
        return ResponseEntity.ok(queue);
    }
}

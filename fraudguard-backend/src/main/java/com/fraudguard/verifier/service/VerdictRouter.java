package com.fraudguard.verifier.service;

import com.fraudguard.verifier.config.VerifierProperties;
import com.fraudguard.verifier.model.RoutingDecision;
import com.fraudguard.verifier.model.Verdict;
import com.fraudguard.verifier.model.VerifierOutput;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * Routes a verified dispute to AUTO_RESOLVED or HUMAN_REVIEW.
 *
 * Logic (from build guide):
 * - UNCERTAIN verdict → always HUMAN_REVIEW
 * - confidence >= threshold AND at least one contradiction flag → AUTO_RESOLVED
 * - All other cases → HUMAN_REVIEW (fail safe default)
 *
 * Requiring a contradiction flag alongside high confidence prevents the model
 * from auto-resolving with a confident assertion backed by zero stated reasoning.
 */
@Service
public class VerdictRouter {

    private static final Logger log = LoggerFactory.getLogger(VerdictRouter.class);

    private final double threshold;

    public VerdictRouter(VerifierProperties props) {
        this.threshold = props.getAutoResolveConfidenceThreshold();
    }

    public RoutingDecision route(VerifierOutput output) {
        if (output.getVerdict() == Verdict.UNCERTAIN) {
            log.info("Routing to HUMAN_REVIEW: verdict is UNCERTAIN");
            return RoutingDecision.HUMAN_REVIEW;
        }

        if (output.getConfidence() >= threshold
                && output.getContradictionFlags() != null
                && !output.getContradictionFlags().isEmpty()) {
            log.info("Routing to AUTO_RESOLVED: confidence={}, flags={}",
                    output.getConfidence(), output.getContradictionFlags());
            return RoutingDecision.AUTO_RESOLVED;
        }

        log.info("Routing to HUMAN_REVIEW: confidence={} (threshold={}), flags={}",
                output.getConfidence(), threshold, output.getContradictionFlags());
        return RoutingDecision.HUMAN_REVIEW;
    }
}

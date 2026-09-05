"""
router.py — Tier routing logic (Python port of TierRouterServiceImpl.java).

Thresholds are percentile-based, computed from the validation set:
  - trivial_max_score  = 0.0575  (33rd percentile of calibrated scores)
  - moderate_max_score = 0.0856  (67th percentile)
  - value_threshold    = 444.95  (90th percentile of TransactionAmt)

OR-logic: either signal alone escalates to HIGH. This is intentional —
182 confirmed fraud cases in the validation set were caught by value override
alone (score below threshold, amount above threshold). Do not change to AND.
"""
from __future__ import annotations

from fraudguard_api.models import EscalationReason, Tier, TierAssignment

# Percentile-based cutoffs from validation set
TRIVIAL_MAX_SCORE: float = 0.0575
MODERATE_MAX_SCORE: float = 0.0856
VALUE_THRESHOLD: float = 444.95


def assign_tier(
    transaction_id: int,
    gbt_score: float,
    transaction_amount: float,
) -> TierAssignment:
    """
    Assign a transaction to a tier using OR-logic escalation.

    HIGH   if score >= moderate_max_score  OR  amount >= value_threshold
    MODERATE if score >= trivial_max_score
    TRIVIAL  otherwise
    """
    score_high = gbt_score >= MODERATE_MAX_SCORE
    value_high = transaction_amount >= VALUE_THRESHOLD

    if score_high and value_high:
        tier = Tier.HIGH
        reason = EscalationReason.BOTH
    elif score_high:
        tier = Tier.HIGH
        reason = EscalationReason.SCORE
    elif value_high:
        tier = Tier.HIGH
        reason = EscalationReason.VALUE
    elif gbt_score >= TRIVIAL_MAX_SCORE:
        tier = Tier.MODERATE
        reason = None
    else:
        tier = Tier.TRIVIAL
        reason = None

    return TierAssignment(
        transaction_id=transaction_id,
        gbt_score=gbt_score,
        transaction_amount=transaction_amount,
        tier=tier,
        escalation_reason=reason,
    )

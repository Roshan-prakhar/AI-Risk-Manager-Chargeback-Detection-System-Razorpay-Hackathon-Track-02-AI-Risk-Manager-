"""
models.py — Pydantic request/response models for all API endpoints.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ReasonCode(str, Enum):
    UNAUTHORIZED_TRANSACTION = "UNAUTHORIZED_TRANSACTION"
    ITEM_NOT_RECEIVED = "ITEM_NOT_RECEIVED"


class Tier(str, Enum):
    TRIVIAL = "TRIVIAL"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class EscalationReason(str, Enum):
    SCORE = "SCORE"
    VALUE = "VALUE"
    BOTH = "BOTH"


class DeliveryStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class Verdict(str, Enum):
    GENUINE_FRAUD = "genuine_fraud"
    FRIENDLY_FRAUD = "friendly_fraud"
    UNCERTAIN = "uncertain"


class RoutingDecision(str, Enum):
    AUTO_RESOLVED = "AUTO_RESOLVED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


# ---------------------------------------------------------------------------
# Stage 1 — Scoring
# ---------------------------------------------------------------------------

class ScoreResponse(BaseModel):
    raw_prob: float = Field(..., description="Raw LightGBM probability before calibration")
    calibrated_prob: float = Field(..., description="Calibrated fraud probability (Platt scaling)")
    decision: int = Field(..., description="1=FRAUD, 0=LEGIT at threshold=0.11")
    threshold: float = Field(0.11)


# ---------------------------------------------------------------------------
# Stage 2 — Tier Routing
# ---------------------------------------------------------------------------

class TierAssignment(BaseModel):
    transaction_id: int
    gbt_score: float
    transaction_amount: float
    tier: Tier
    escalation_reason: Optional[EscalationReason] = None


# ---------------------------------------------------------------------------
# Stage 3 — Evidence Cache
# ---------------------------------------------------------------------------

class EvidenceSnapshot(BaseModel):
    transaction_id: int
    gbt_score: float
    tier: Tier
    transaction_amount: float
    delivery_status: DeliveryStatus = DeliveryStatus.PENDING
    delivery_confirmed_at: Optional[str] = None
    cached_at: Optional[str] = None
    feature_snapshot: Optional[dict] = None


class DeliveryConfirmRequest(BaseModel):
    confirmed_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Combined process endpoint (Stage 1 + 2 + 3)
# ---------------------------------------------------------------------------

class ProcessResponse(BaseModel):
    scoring: ScoreResponse
    routing: TierAssignment
    evidence_cached: bool


# ---------------------------------------------------------------------------
# Stage 4 — LLM Verifier
# ---------------------------------------------------------------------------

class DisputeRequest(BaseModel):
    transaction_id: int = Field(..., alias="transactionId")
    reason_code: ReasonCode = Field(..., alias="reasonCode")
    customer_text: str = Field(..., alias="customerText")

    model_config = {"populate_by_name": True}


class DisputeVerdict(BaseModel):
    transaction_id: int
    reason_code: ReasonCode
    verdict: Verdict
    confidence: float
    contradiction_flags: List[str]
    evidence_summary: str
    routing_decision: RoutingDecision
    customer_text: str

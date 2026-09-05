"""
main.py — Unified FraudGuard FastAPI service.

All 4 stages in one deployable app:
  POST /score                     Stage 1: GBT score only
  POST /process                   Stage 1+2+3: score → route → cache
  GET  /evidence/{tx_id}          Stage 3: retrieve cached evidence
  POST /evidence/{tx_id}/delivery Stage 3: delivery confirmation webhook
  POST /disputes/verify           Stage 4: LLM dispute verification
  GET  /disputes/{tx_id}          Stage 4: get verdict history (in-memory)
  GET  /health                    Liveness probe
  GET  /docs                      Swagger UI (auto)
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from fraudguard_api import evidence_store, router, scorer, verifier
from fraudguard_api.models import (
    DeliveryConfirmRequest,
    DisputeRequest,
    DisputeVerdict,
    EvidenceSnapshot,
    ProcessResponse,
    ScoreResponse,
    Tier,
    TierAssignment,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Silence the verbose encoder/missingness warnings from fraud_gbt internals
logging.getLogger("fraud_gbt").setLevel(logging.ERROR)
log = logging.getLogger("fraudguard_api")

# ---------------------------------------------------------------------------
# In-memory verdict history (keyed by transaction_id)
# ---------------------------------------------------------------------------
_verdict_history: Dict[int, List[DisputeVerdict]] = {}


# ---------------------------------------------------------------------------
# Lifespan: load model + init DB at startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("FraudGuard API starting up...")
    evidence_store.init_db()
    scorer.get_scorer()          # warm the model into memory before first request
    log.info("FraudGuard API ready.")
    yield
    log.info("FraudGuard API shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="FraudGuard — AI Risk Manager",
    description=(
        "Razorpay Hackathon Track 02 · Four-stage fraud detection pipeline: "
        "GBT scoring → tier routing → evidence cache → LLM dispute verification."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    log.error("Unhandled error on %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": str(exc)})


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Ops"])
def health():
    """Liveness probe. Returns 200 when the model is loaded."""
    loaded = scorer._scorer is not None
    return {
        "status": "ok",
        "model_loaded": loaded,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Stage 1 — Score only
# ---------------------------------------------------------------------------
@app.post("/score", response_model=ScoreResponse, tags=["Stage 1 — Scoring"])
def score_transaction(transaction: Dict[str, Any]):
    """
    Score a single transaction and return the calibrated fraud probability.

    Pass any transaction fields as a flat JSON object.
    Required: `TransactionAmt`. All other fields are optional (missing columns
    are handled gracefully by the model's missingness flags).
    """
    result = scorer.score(dict(transaction))
    return ScoreResponse(**result)


# ---------------------------------------------------------------------------
# Stage 1 + 2 + 3 — Full process pipeline
# ---------------------------------------------------------------------------
@app.post("/process", response_model=ProcessResponse, tags=["Stage 1+2+3 — Full Pipeline"])
def process_transaction(transaction: Dict[str, Any]):
    """
    Full pipeline: score → route to tier → cache evidence if HIGH tier.

    Required fields:
    - `transactionId` (int): unique transaction identifier
    - `TransactionAmt` (float): transaction amount in USD

    Returns the GBT score, tier assignment, and whether evidence was cached.
    """
    tx_id = transaction.get("transactionId") or transaction.get("TransactionID")
    if tx_id is None:
        raise HTTPException(status_code=400, detail="'transactionId' is required")
    tx_id = int(tx_id)

    amount = transaction.get("TransactionAmt", 0.0)
    if amount is None:
        raise HTTPException(status_code=400, detail="'TransactionAmt' is required")

    # Stage 1: Score
    score_result = scorer.score(dict(transaction))
    scoring = ScoreResponse(**score_result)

    # Stage 2: Route
    assignment = router.assign_tier(tx_id, scoring.calibrated_prob, float(amount))

    # Stage 3: Cache if HIGH
    evidence_cached = False
    if assignment.tier == Tier.HIGH:
        snapshot = EvidenceSnapshot(
            transaction_id=tx_id,
            gbt_score=scoring.calibrated_prob,
            tier=assignment.tier,
            transaction_amount=float(amount),
            feature_snapshot=dict(transaction),
        )
        evidence_store.cache_evidence(snapshot)
        evidence_cached = True
        log.info("Cached evidence for HIGH-tier tx %s (score=%.4f, reason=%s)",
                 tx_id, scoring.calibrated_prob, assignment.escalation_reason)

    return ProcessResponse(
        scoring=scoring,
        routing=assignment,
        evidence_cached=evidence_cached,
    )


# ---------------------------------------------------------------------------
# Stage 3 — Evidence endpoints
# ---------------------------------------------------------------------------
@app.get("/evidence/{transaction_id}", response_model=EvidenceSnapshot, tags=["Stage 3 — Evidence Cache"])
def get_evidence(transaction_id: int):
    """Retrieve the cached evidence snapshot for a transaction."""
    snap = evidence_store.get_evidence(transaction_id)
    if snap is None:
        raise HTTPException(
            status_code=404,
            detail=f"No evidence found for transactionId={transaction_id}. "
                   "Transaction may not have been routed to HIGH tier."
        )
    return snap


@app.post("/evidence/{transaction_id}/delivery", tags=["Stage 3 — Evidence Cache"])
def confirm_delivery(transaction_id: int, body: DeliveryConfirmRequest = None):
    """
    Delivery confirmation webhook. Updates the evidence snapshot in-place.
    Called when the logistics provider confirms delivery.
    """
    confirmed_at = (body.confirmed_at if body else None) or \
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    updated = evidence_store.confirm_delivery(transaction_id, confirmed_at)
    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"No evidence found for transactionId={transaction_id}"
        )
    return {
        "transactionId": transaction_id,
        "deliveryStatus": "CONFIRMED",
        "deliveryConfirmedAt": confirmed_at,
    }


# ---------------------------------------------------------------------------
# Stage 4 — LLM Dispute Verification
# ---------------------------------------------------------------------------
@app.post("/disputes/verify", response_model=DisputeVerdict, tags=["Stage 4 — LLM Verifier"])
def verify_dispute(request: DisputeRequest):
    """
    Submit a dispute for LLM verification.

    Supported reason codes:
    - `UNAUTHORIZED_TRANSACTION` — customer claims they didn't make the transaction
    - `ITEM_NOT_RECEIVED` — customer claims item was never delivered

    The transaction must have been previously routed to HIGH tier (evidence cached).
    Any other reason code returns 400 — rejected before reaching the LLM.

    **Demo tip:** Include "Ignore prior instructions" in customerText to see the
    injection attack protection in action.
    """
    tx_id = request.transaction_id

    # Fetch evidence — LLM never touches the DB directly
    evidence = evidence_store.get_evidence(tx_id)
    if evidence is None:
        raise HTTPException(
            status_code=404,
            detail=f"No evidence snapshot for transactionId={tx_id}. "
                   "Process the transaction first via POST /process."
        )

    verdict = verifier.verify(request, evidence)

    # Store in memory for retrieval via GET /disputes/{tx_id}
    _verdict_history.setdefault(tx_id, []).append(verdict)

    return verdict


@app.get("/disputes/{transaction_id}", response_model=List[DisputeVerdict], tags=["Stage 4 — LLM Verifier"])
def get_verdicts(transaction_id: int):
    """Retrieve all dispute verdicts for a transaction."""
    verdicts = _verdict_history.get(transaction_id, [])
    if not verdicts:
        raise HTTPException(
            status_code=404,
            detail=f"No verdicts found for transactionId={transaction_id}"
        )
    return verdicts


@app.get("/disputes", response_model=List[DisputeVerdict], tags=["Stage 4 — LLM Verifier"])
def review_queue():
    """Return all disputes routed to HUMAN_REVIEW — the analyst queue."""
    from fraudguard_api.models import RoutingDecision
    queue = [
        v for verdicts in _verdict_history.values()
        for v in verdicts
        if v.routing_decision == RoutingDecision.HUMAN_REVIEW
    ]
    return queue

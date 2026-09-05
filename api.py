"""
api.py — FastAPI wrapper for the GBT Fraud Scorer.

Run with:  uvicorn api:app --host 0.0.0.0 --port 8000
"""
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("api")

# ---------------------------------------------------------------------------
# Global scorer (loaded once at startup)
# ---------------------------------------------------------------------------
scorer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global scorer
    from fraud_gbt import config as cfg
    from fraud_gbt.serving.score import load_scorer
    
    log.info("Loading FraudScorer...")
    scorer = load_scorer(
        model_path=str(cfg.MODEL_PATH),
        calibrator_path=str(cfg.CALIBRATOR_PATH),
        encoder_path=str(cfg.ENCODER_PATH),
        train_stats_path=str(cfg.TRAIN_STATS_PATH),
        threshold=0.11,  # optimal threshold from metrics_report.json
    )
    log.info("FraudScorer loaded successfully.")
    yield
    log.info("Shutting down.")

app = FastAPI(
    title="GBT Fraud Scorer API",
    version="1.0.0",
    lifespan=lifespan,
)


class TransactionRequest(BaseModel):
    """Transaction fields to score. Accepts any key-value pairs."""
    class Config:
        extra = "allow"


class ScoringResponse(BaseModel):
    raw_prob: float
    calibrated_prob: float
    decision: int
    threshold: float


@app.post("/score", response_model=ScoringResponse)
def score_transaction(tx: TransactionRequest):
    """Score a single transaction and return fraud probability + decision."""
    if scorer is None:
        raise HTTPException(status_code=503, detail="Scorer not loaded yet.")
    
    tx_dict = tx.model_dump()
    result = scorer.score_transaction(tx_dict)
    return ScoringResponse(**result)


@app.get("/health")
def health():
    return {"status": "ok", "scorer_loaded": scorer is not None}


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)

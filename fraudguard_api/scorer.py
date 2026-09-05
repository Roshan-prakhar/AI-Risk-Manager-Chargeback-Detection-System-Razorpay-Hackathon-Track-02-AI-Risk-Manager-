"""
scorer.py — Thin wrapper around fraud_gbt.serving.score.
Loads the model once at startup; reused across all requests.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure repo root is on path so fraud_gbt is importable on Render
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

log = logging.getLogger(__name__)

_scorer = None


def get_scorer():
    """Return the singleton FraudScorer, loading it on first call."""
    global _scorer
    if _scorer is None:
        _scorer = _load()
    return _scorer


def _load():
    from fraud_gbt import config as cfg
    from fraud_gbt.serving.score import load_scorer

    log.info("Loading FraudScorer from %s", cfg.MODEL_PATH)
    scorer = load_scorer(
        model_path=str(cfg.MODEL_PATH),
        calibrator_path=str(cfg.CALIBRATOR_PATH),
        encoder_path=str(cfg.ENCODER_PATH),
        train_stats_path=str(cfg.TRAIN_STATS_PATH),
        threshold=0.11,
    )
    log.info("FraudScorer loaded (threshold=0.11)")
    return scorer


def score(transaction: dict) -> dict:
    """
    Score a single transaction dict.
    Returns: {raw_prob, calibrated_prob, decision, threshold}
    """
    return get_scorer().score_transaction(transaction)

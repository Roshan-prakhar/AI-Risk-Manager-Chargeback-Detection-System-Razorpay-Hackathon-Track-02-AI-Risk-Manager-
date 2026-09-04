"""
serving/score.py
----------------
Load model + calibrator and score a single new transaction.

Design notes
------------
This module is the production interface.  It must be callable standalone
without importing anything from the training pipeline.  The only inputs are:
  1. A transaction dict (the raw fields, pre-feature-engineering)
  2. The saved model artifact, calibrator, encoder map, and card stats

It applies the full pipeline in sequence:
  raw fields → feature engineering → encoding → model → calibration → decision

The output dict includes raw_prob, calibrated_prob, and decision so callers
can log the full score for audit, not just the binary flag.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class FraudScorer:
    """Load all artifacts and score new transactions.

    Parameters
    ----------
    model_path : str
        Path to the saved LightGBM model text file.
    calibrator_path : str
        Path to the saved calibrator (joblib).
    encoder_path : str
        Path to the saved categorical encoder map (joblib).
    train_stats_path : str
        Path to the saved card stats dict (joblib) with keys
        ``{card_stats, global_mean, global_std, card_freq}``.
    threshold : float
        Decision threshold to apply to calibrated probabilities.
    feature_cols : list[str]
        Ordered list of feature column names.
    missingness_cols : list[str]
        Columns for which to generate missingness flags.
    """

    def __init__(
        self,
        model_path: str,
        calibrator_path: str,
        encoder_path: str,
        train_stats_path: str,
        threshold: float,
        feature_cols: list[str],
        missingness_cols: list[str],
        card_col: str = "card1",
    ) -> None:
        self.threshold        = threshold
        self.feature_cols     = feature_cols
        self.missingness_cols = missingness_cols
        self.card_col         = card_col

        log.info("Loading model from %s", model_path)
        self.model = lgb.Booster(model_file=model_path)

        log.info("Loading calibrator from %s", calibrator_path)
        self.calibrator = joblib.load(calibrator_path)

        log.info("Loading encoder from %s", encoder_path)
        self.encoder_map = joblib.load(encoder_path)

        log.info("Loading train stats from %s", train_stats_path)
        stats = joblib.load(train_stats_path)
        self.card_stats  = stats["card_stats"]
        self.global_mean = stats["global_mean"]
        self.global_std  = stats["global_std"]
        self.card_freq   = stats["card_freq"]

        log.info("FraudScorer ready. Threshold=%.4f", threshold)

    def score_transaction(self, transaction: dict[str, Any]) -> dict[str, Any]:
        """Score a single transaction through the full pipeline.

        Parameters
        ----------
        transaction : dict
            Raw transaction fields (as they would appear in the CSV).
            Missing fields are tolerated; they will produce NaN / 0.

        Returns
        -------
        dict with keys:
            - ``raw_prob``         : raw GBT output probability
            - ``calibrated_prob``  : after Platt/isotonic calibration
            - ``decision``         : 1 (flag as fraud) or 0 (pass)
            - ``threshold``        : decision threshold used
        """
        # Build a single-row DataFrame from the input dict
        df = pd.DataFrame([transaction])

        # Feature engineering
        df = self._build_features(df)

        # Categorical encoding
        df = self._encode_cats(df)

        # Select and order feature columns; fill any missing with 0
        X = df.reindex(columns=self.feature_cols, fill_value=0.0).values

        # Raw prediction
        raw_prob = float(self.model.predict(X)[0])

        # Calibration
        calibrated_prob = float(
            self._apply_calibration(np.array([raw_prob]))[0]
        )

        decision = int(calibrated_prob >= self.threshold)

        result = {
            "raw_prob":        round(raw_prob, 6),
            "calibrated_prob": round(calibrated_prob, 6),
            "decision":        decision,
            "threshold":       self.threshold,
        }
        log.debug(
            "Scored transaction: raw=%.4f, calib=%.4f, decision=%d",
            raw_prob, calibrated_prob, decision,
        )
        return result

    def score_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Score a batch of transactions.

        Parameters
        ----------
        df : pd.DataFrame
            Each row is a transaction.

        Returns
        -------
        pd.DataFrame
            Original *df* with columns ``raw_prob``, ``calibrated_prob``,
            ``decision`` appended.
        """
        df = df.copy()
        df_feat = self._build_features(df)
        df_feat = self._encode_cats(df_feat)
        X = df_feat.reindex(columns=self.feature_cols, fill_value=0.0).values

        raw_probs       = self.model.predict(X)
        calibrated_probs = self._apply_calibration(raw_probs)

        df["raw_prob"]        = raw_probs
        df["calibrated_prob"] = calibrated_probs
        df["decision"]        = (calibrated_probs >= self.threshold).astype(int)
        return df

    # ------------------------------------------------------------------
    # Internal pipeline steps
    # ------------------------------------------------------------------

    def _build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        from fraud_gbt.features.build_features import (
            add_amount_deviation,
            add_missingness_flags,
            add_novelty_flags,
        )
        df = add_amount_deviation(
            df, self.card_stats, self.global_mean, self.global_std, self.card_col
        )
        df = add_novelty_flags(df, self.card_freq, self.card_col)
        df = add_missingness_flags(df, self.missingness_cols)
        return df

    def _encode_cats(self, df: pd.DataFrame) -> pd.DataFrame:
        from fraud_gbt.features.encoders import apply_categorical_encoder
        return apply_categorical_encoder(df, self.encoder_map)

    def _apply_calibration(self, raw_probs: np.ndarray) -> np.ndarray:
        from fraud_gbt.models.calibrate import apply_calibration
        return apply_calibration(self.calibrator, raw_probs)


# ---------------------------------------------------------------------------
# Convenience loader
# ---------------------------------------------------------------------------

def load_scorer(
    model_path: str,
    calibrator_path: str,
    encoder_path: str,
    train_stats_path: str,
    threshold: float,
    feature_cols: list[str] | None = None,
    missingness_cols: list[str] | None = None,
    card_col: str = "card1",
) -> FraudScorer:
    """Construct and return a ready-to-use FraudScorer.

    Parameters mirror ``FraudScorer.__init__``.
    If feature_cols is None, loads from cfg.FEATURE_COLS_PATH.
    If missingness_cols is None, loads from cfg.MISSINGNESS_FLAG_COLS.
    """
    if feature_cols is None:
        import joblib
        from fraud_gbt import config as cfg
        feature_cols = joblib.load(cfg.FEATURE_COLS_PATH)

    if missingness_cols is None:
        from fraud_gbt import config as cfg
        missingness_cols = cfg.MISSINGNESS_FLAG_COLS

    return FraudScorer(
        model_path=model_path,
        calibrator_path=calibrator_path,
        encoder_path=encoder_path,
        train_stats_path=train_stats_path,
        threshold=threshold,
        feature_cols=feature_cols,
        missingness_cols=missingness_cols,
        card_col=card_col,
    )

"""
models/calibrate.py
-------------------
Post-hoc probability calibration for class-weighted GBT models.

Design notes
------------
Class-weighted training (scale_pos_weight / oversampling) is a well-documented
source of probability distortion: it shifts raw predicted probabilities away
from their true likelihood.  This is NOT a bug specific to our build; it is a
known, documented effect of any imbalance-handling technique that reweights
the loss function.

The standard fix is a post-hoc calibration step:
  - Platt scaling (logistic regression on raw scores): simpler, safer with
    smaller calibration sets.  Recommended default for our dataset size.
  - Isotonic regression: more flexible, but needs more data to avoid
    overfitting the calibration mapping itself.

The calibrator is always fit on a DEDICATED calibration split that is:
  (a) separate from train and val (the model must never have seen these rows)
  (b) separate from the final test set (never contaminate test evaluation)

After calibration, a threshold of 0.5 (or any fixed threshold) means the
same thing consistently going forward, without re-derivation every retrain.
"""

from __future__ import annotations

import logging
from typing import Callable

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fit_calibrator(
    raw_probs_on_calib_split: np.ndarray,
    y_calib: np.ndarray,
    method: str = "platt",
) -> object:
    """Fit a probability calibrator on the dedicated calibration split.

    Parameters
    ----------
    raw_probs_on_calib_split : np.ndarray, shape (n,)
        Raw model probabilities (output of ``model.predict()``) evaluated on
        the **calibration split only**.  Never pass train, val, or test data.
    y_calib : np.ndarray, shape (n,)
        True fraud labels for the calibration split.
    method : str
        ``"platt"``  (default) — logistic regression on raw scores.
                                  Simpler, safer with our data size.
        ``"isotonic"`` — non-parametric isotonic regression.
                         More flexible, needs more data; risks overfitting
                         the calibration mapping with small splits.

    Returns
    -------
    Fitted calibrator object.  Pass to ``apply_calibration``.

    Raises
    ------
    ValueError
        If *method* is not one of ``"platt"`` or ``"isotonic"``.
    """
    raw = np.asarray(raw_probs_on_calib_split, dtype=float).ravel()
    y   = np.asarray(y_calib, dtype=int).ravel()

    if len(raw) != len(y):
        raise ValueError(
            f"raw_probs and y_calib must have the same length; "
            f"got {len(raw)} and {len(y)}."
        )

    n_pos = y.sum()
    n_neg = len(y) - n_pos
    log.info(
        "Fitting calibrator ('%s') on %d calib rows "
        "(%d fraud, %d non-fraud).",
        method, len(y), n_pos, n_neg,
    )

    if method == "platt":
        calibrator = _fit_platt(raw, y)
    elif method == "isotonic":
        calibrator = _fit_isotonic(raw, y)
    else:
        raise ValueError(
            f"Unknown calibration method '{method}'. "
            "Choose 'platt' or 'isotonic'."
        )

    # Quick diagnostic: compare raw vs calibrated mean
    calib_probs = apply_calibration(calibrator, raw)
    log.info(
        "  Raw probs   — mean: %.4f, std: %.4f, min: %.4f, max: %.4f",
        raw.mean(), raw.std(), raw.min(), raw.max(),
    )
    log.info(
        "  Calib probs — mean: %.4f, std: %.4f, min: %.4f, max: %.4f",
        calib_probs.mean(), calib_probs.std(),
        calib_probs.min(), calib_probs.max(),
    )

    return calibrator


def apply_calibration(
    calibrator: object,
    raw_probs: np.ndarray,
) -> np.ndarray:
    """Apply a fitted calibrator to new raw model probabilities.

    This function is designed to be used standalone at serving time, not just
    inside training scripts.  It requires only the saved calibrator object
    and the raw probabilities to convert.

    Parameters
    ----------
    calibrator : object
        Fitted calibrator from ``fit_calibrator``.
    raw_probs : np.ndarray, shape (n,)
        Raw model probabilities to convert.

    Returns
    -------
    np.ndarray, shape (n,)
        Calibrated probabilities in [0, 1].
    """
    raw = np.asarray(raw_probs, dtype=float).ravel()

    if isinstance(calibrator, LogisticRegression):
        # Platt: logistic regression was fit on raw probabilities as the
        # single feature.
        calibrated = calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]
    elif isinstance(calibrator, IsotonicRegression):
        calibrated = calibrator.predict(raw)
    else:
        raise TypeError(
            f"Unrecognised calibrator type: {type(calibrator).__name__}. "
            "Expected LogisticRegression (Platt) or IsotonicRegression."
        )

    # Clip to valid probability range (isotonic can produce tiny overshoot)
    calibrated = np.clip(calibrated, 0.0, 1.0)
    return calibrated.astype(float)


def save_calibrator(calibrator: object, path: str) -> None:
    """Persist calibrator to disk with joblib."""
    joblib.dump(calibrator, path)
    log.info("Calibrator saved to %s", path)


def load_calibrator(path: str) -> object:
    """Load a persisted calibrator from disk."""
    calibrator = joblib.load(path)
    log.info("Calibrator loaded from %s", path)
    return calibrator


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _fit_platt(raw: np.ndarray, y: np.ndarray) -> LogisticRegression:
    """Fit logistic regression (Platt scaling) on raw probabilities."""
    lr = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
    lr.fit(raw.reshape(-1, 1), y)
    return lr


def _fit_isotonic(raw: np.ndarray, y: np.ndarray) -> IsotonicRegression:
    """Fit isotonic regression calibrator on raw probabilities."""
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(raw, y)
    return iso

"""
models/train.py
---------------
GBT training with conservative hyper-parameters, monotonic constraints,
and post-training sanity checks.

Design notes
------------
* learning_rate=0.01 + strong regularisation: we found that lr=0.05 with a
  high scale_pos_weight caused the model to early-stop after a single tree —
  validation AUC degraded every round after round 1.  Lower lr + stronger
  reg fixed this and improved AUC.

* Single-digit tree count guard: a model with < 10 trees after a budget of
  2000 is a red flag.  It almost always means early stopping fired
  immediately because of a mis-configured validation metric or a degenerate
  probability distribution from the imbalanced weights.  Log loudly; do not
  silently accept it.

* Class weighting: scale_pos_weight = (n_neg / n_pos) is used to handle
  the ~3.5% fraud rate.  This SHIFTS raw predicted probabilities away from
  calibrated probabilities — which is why a dedicated calibration step is
  always required after training (see calibrate.py).
"""

from __future__ import annotations

import logging
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Minimum acceptable tree count; log a warning below this
MIN_TREE_COUNT_WARN = 10


def train_gbt(
    X_train: pd.DataFrame | np.ndarray,
    y_train: pd.Series | np.ndarray,
    X_val: pd.DataFrame | np.ndarray,
    y_val: pd.Series | np.ndarray,
    feature_cols: list[str],
    monotonic_vector: list[int],
    params: dict[str, Any] | None = None,
    n_estimators: int = 2000,
    early_stopping_rounds: int = 50,
) -> tuple[lgb.Booster, dict]:
    """Train a LightGBM GBT with monotonic constraints and early stopping.

    Parameters
    ----------
    X_train, y_train : array-like
        Training features and labels.
    X_val, y_val : array-like
        Validation features and labels (for early stopping — NOT calibration).
    feature_cols : list[str]
        Ordered list of feature column names; must match columns of X_train.
    monotonic_vector : list[int]
        Per-feature monotonic constraint directions (+1 / -1 / 0).
        Same length as *feature_cols*.  Use ``get_constraint_vector`` from
        ``models/monotonic_config.py`` to generate this.
    params : dict, optional
        LightGBM parameter dict.  Defaults to ``config.LGB_PARAMS``.
    n_estimators : int
        Maximum number of boosting rounds.
    early_stopping_rounds : int
        Stop if validation AUC has not improved for this many rounds.

    Returns
    -------
    tuple[lgb.Booster, dict]
        Trained model and a training history dict with keys:
        ``["best_iteration", "best_score", "num_trees"]``.
    """
    # Import here to avoid circular deps with config at module level
    from fraud_gbt.config import LGB_PARAMS

    lgb_params = dict(params or LGB_PARAMS)

    # Compute class weight
    y_arr = np.asarray(y_train)
    n_neg = (y_arr == 0).sum()
    n_pos = (y_arr == 1).sum()
    if n_pos == 0:
        raise ValueError("Training set has zero positive (fraud) examples.")
    scale_pos_weight = n_neg / n_pos
    lgb_params["scale_pos_weight"] = scale_pos_weight
    log.info(
        "Class ratio: %d neg / %d pos -> scale_pos_weight = %.2f",
        n_neg, n_pos, scale_pos_weight,
    )

    # Inject monotonic constraints
    if len(monotonic_vector) != len(feature_cols):
        raise ValueError(
            f"monotonic_vector length ({len(monotonic_vector)}) must match "
            f"feature_cols length ({len(feature_cols)})."
        )
    lgb_params["monotone_constraints"] = monotonic_vector
    lgb_params["monotone_constraints_method"] = "advanced"

    # Build LightGBM datasets
    dtrain = lgb.Dataset(
        X_train,
        label=y_arr,
        feature_name=feature_cols,
        free_raw_data=False,
    )
    dval = lgb.Dataset(
        X_val,
        label=np.asarray(y_val),
        feature_name=feature_cols,
        reference=dtrain,
        free_raw_data=False,
    )

    evals_result: dict = {}
    callbacks = [
        lgb.early_stopping(stopping_rounds=early_stopping_rounds, verbose=False),
        lgb.log_evaluation(period=100),
        lgb.record_evaluation(evals_result),
    ]

    log.info(
        "Training LightGBM: max_rounds=%d, lr=%.4f, num_leaves=%d, "
        "early_stopping=%d",
        n_estimators,
        lgb_params.get("learning_rate", "?"),
        lgb_params.get("num_leaves", "?"),
        early_stopping_rounds,
    )

    model = lgb.train(
        lgb_params,
        dtrain,
        num_boost_round=n_estimators,
        valid_sets=[dtrain, dval],
        valid_names=["train", "val"],
        callbacks=callbacks,
    )

    num_trees = model.num_trees()
    best_iter = model.best_iteration
    best_score = model.best_score.get("val", {}).get("auc", None)

    history = {
        "best_iteration": best_iter,
        "best_score":     best_score,
        "num_trees":      num_trees,
        "evals_result":   evals_result,
    }

    log.info(
        "Training complete: %d trees, best_iteration=%d, val_AUC=%.5f",
        num_trees, best_iter, best_score or -1,
    )

    # -----------------------------------------------------------------------
    # Post-training sanity guard
    # A single-digit tree count after a large budget almost always means
    # early stopping misfired (wrong metric, degenerate class weights, etc.).
    # Log loudly; do NOT silently accept.
    # -----------------------------------------------------------------------
    if num_trees < MIN_TREE_COUNT_WARN:
        log.error(
            "[RED FLAG] model has only %d trees after a budget of %d rounds. "
            "Possible causes: (1) scale_pos_weight too high -> validation AUC "
            "degrades every round after round 1; (2) wrong eval metric; "
            "(3) val set has no positive examples.  Investigate before using "
            "this model.",
            num_trees, n_estimators,
        )

    return model, history


def get_feature_importance(
    model: lgb.Booster,
    feature_cols: list[str],
    importance_type: str = "gain",
) -> pd.DataFrame:
    """Return a ranked feature importance DataFrame.

    Parameters
    ----------
    model : lgb.Booster
    feature_cols : list[str]
    importance_type : str
        ``"gain"`` (default) or ``"split"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``["feature", "importance"]``, sorted descending.
    """
    imp = model.feature_importance(importance_type=importance_type)
    return (
        pd.DataFrame({"feature": feature_cols, "importance": imp})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )

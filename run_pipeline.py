"""
run_pipeline.py
---------------
End-to-end orchestration: load → split → features → encode → train →
calibrate → evaluate → monitor → save artifacts.

Run from the project root:
    python run_pipeline.py

All configurable values (paths, hyper-parameters, cost matrix) live in
fraud_gbt/config.py — edit that file, not this one.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Logging setup (before any imports that might log)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("run_pipeline")

# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------
from fraud_gbt import config as cfg
from fraud_gbt.data.loader import load_transactions, load_identity, merge_identity
from fraud_gbt.data.time_split import time_based_split
from fraud_gbt.features.build_features import (
    build_all_features,
    compute_card_stats,
    compute_train_frequencies,
)
from fraud_gbt.features.encoders import (
    apply_categorical_encoder,
    fit_categorical_encoder,
)
from fraud_gbt.features.recurrence import validate_recurrence_signal
from fraud_gbt.models.calibrate import (
    apply_calibration,
    fit_calibrator,
    save_calibrator,
)
from fraud_gbt.models.monotonic_config import get_constraint_vector
from fraud_gbt.models.train import get_feature_importance, train_gbt
from fraud_gbt.evaluation.threshold_selection import (
    find_optimal_threshold,
    plot_cost_curve,
    sweep_thresholds_by_cost,
)
from fraud_gbt.evaluation.metrics_report import generate_report
from fraud_gbt.monitoring.drift_psi import psi_report, save_reference_snapshot
from fraud_gbt.monitoring.leaf_index import LeafIndex


# ===========================================================================
# STEP 1 — Load data
# ===========================================================================
def step_load() -> pd.DataFrame:
    log.info("=" * 60)
    log.info("STEP 1: Loading data")
    log.info("=" * 60)

    if not cfg.TRANSACTION_CSV.exists():
        log.error(
            "Transaction CSV not found at %s. "
            "Update DATA_DIR in config.py and re-run.",
            cfg.TRANSACTION_CSV,
        )
        sys.exit(1)

    tx = load_transactions(
        str(cfg.TRANSACTION_CSV),
        dtype_map=cfg.DTYPE_MAP,
        drop_columns=[],          # keep TransactionID for the join
    )

    if cfg.IDENTITY_CSV.exists():
        identity = load_identity(str(cfg.IDENTITY_CSV))
        df = merge_identity(tx, identity, join_key=cfg.ID_COL)
    else:
        log.warning(
            "Identity CSV not found at %s. "
            "Proceeding without identity features.",
            cfg.IDENTITY_CSV,
        )
        df = tx.copy()
        df["has_identity_data"] = 0

    # Drop ID column now that join is complete
    df = df.drop(columns=[cfg.ID_COL], errors="ignore")
    return df


# ===========================================================================
# STEP 2 — Time-based split
# ===========================================================================
def step_split(df: pd.DataFrame):
    log.info("=" * 60)
    log.info("STEP 2: Time-based split")
    log.info("=" * 60)
    train, val, calib, test = time_based_split(
        df,
        dt_col=cfg.TIME_COL,
        train_frac=cfg.TRAIN_FRAC,
        val_frac=cfg.VAL_FRAC,
        calib_frac=cfg.CALIB_FRAC,
    )
    return train, val, calib, test


# ===========================================================================
# STEP 3 — Feature engineering  (fit on train, apply to all splits)
# ===========================================================================
def step_features(train, val, calib, test):
    log.info("=" * 60)
    log.info("STEP 3: Feature engineering")
    log.info("=" * 60)

    # --- Validate recurrence signal before building features ---
    for id_col in ["card1"]:
        if id_col in train.columns and cfg.LABEL_COL in train.columns:
            lift = validate_recurrence_signal(train, id_col, cfg.LABEL_COL)
            if lift < cfg.MIN_RECURRENCE_LIFT:
                log.info(
                    "  Skipping recurrence feature for '%s' (lift=%.3f < %.1f).",
                    id_col, lift, cfg.MIN_RECURRENCE_LIFT,
                )

    # --- Compute stats from TRAIN ONLY ---
    card_stats  = compute_card_stats(train)
    global_mean = float(train["TransactionAmt"].mean())
    global_std  = float(train["TransactionAmt"].std())
    card_freq   = compute_train_frequencies(train, "card1")

    # --- Apply to all splits ---
    kw = dict(
        card_stats=card_stats,
        global_mean=global_mean,
        global_std=global_std,
        card_freq=card_freq,
        missingness_cols=cfg.MISSINGNESS_FLAG_COLS,
    )
    train = build_all_features(train, **kw)
    val   = build_all_features(val,   **kw)
    calib = build_all_features(calib, **kw)
    test  = build_all_features(test,  **kw)

    # Persist stats for serving time
    cfg.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "card_stats":   card_stats,
            "global_mean":  global_mean,
            "global_std":   global_std,
            "card_freq":    card_freq,
        },
        cfg.TRAIN_STATS_PATH,
    )
    log.info("Train stats saved to %s", cfg.TRAIN_STATS_PATH)

    return train, val, calib, test


# ===========================================================================
# STEP 4 — Categorical encoding  (fit on train, apply to all splits)
# ===========================================================================
def step_encode(train, val, calib, test):
    log.info("=" * 60)
    log.info("STEP 4: Categorical encoding")
    log.info("=" * 60)

    available_cats = [c for c in cfg.CAT_COLS if c in train.columns]
    encoder_map = fit_categorical_encoder(train, available_cats)

    train = apply_categorical_encoder(train, encoder_map)
    val   = apply_categorical_encoder(val,   encoder_map)
    calib = apply_categorical_encoder(calib, encoder_map)
    test  = apply_categorical_encoder(test,  encoder_map)

    joblib.dump(encoder_map, cfg.ENCODER_PATH)
    log.info("Encoder saved to %s", cfg.ENCODER_PATH)

    return train, val, calib, test, encoder_map


# ===========================================================================
# STEP 5 — Build X / y matrices and resolve feature columns
# ===========================================================================
def step_build_matrices(train, val, calib, test):
    log.info("=" * 60)
    log.info("STEP 5: Build X / y matrices")
    log.info("=" * 60)

    # Exclude non-feature columns and any remaining non-numeric dtypes.
    # Use pd.api.types.is_numeric_dtype() rather than dtype != object:
    # pandas 2.x StringDtype is NOT caught by != object, so string identity
    # columns that slipped through encoding would crash LightGBM.
    exclude = {cfg.LABEL_COL, cfg.TIME_COL}
    feature_cols = [
        c for c in train.columns
        if c not in exclude and pd.api.types.is_numeric_dtype(train[c])
    ]
    log.info("  Feature count: %d", len(feature_cols))

    def _xy(df):
        X = df[feature_cols].copy()
        y = df[cfg.LABEL_COL].values if cfg.LABEL_COL in df.columns else None
        return X, y

    X_train, y_train = _xy(train)
    X_val,   y_val   = _xy(val)
    X_calib, y_calib = _xy(calib)
    X_test,  y_test  = _xy(test)

    joblib.dump(feature_cols, cfg.FEATURE_COLS_PATH)
    log.info("Feature columns saved to %s", cfg.FEATURE_COLS_PATH)

    return (X_train, y_train, X_val, y_val,
            X_calib, y_calib, X_test, y_test,
            feature_cols)


# ===========================================================================
# STEP 6 — Train GBT with monotonic constraints
# ===========================================================================
def step_train(X_train, y_train, X_val, y_val, feature_cols):
    log.info("=" * 60)
    log.info("STEP 6: Train GBT")
    log.info("=" * 60)

    monotonic_vector = get_constraint_vector(feature_cols)
    n_constrained = sum(1 for v in monotonic_vector if v != 0)
    log.info(
        "  Monotonic constraints: %d / %d features constrained.",
        n_constrained, len(feature_cols),
    )

    model, history = train_gbt(
        X_train, y_train, X_val, y_val,
        feature_cols=feature_cols,
        monotonic_vector=monotonic_vector,
        n_estimators=cfg.LGB_N_ESTIMATORS,
        early_stopping_rounds=cfg.LGB_EARLY_STOPPING,
    )

    # Save model
    cfg.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_model(str(cfg.MODEL_PATH))
    log.info("Model saved to %s", cfg.MODEL_PATH)

    # Feature importance (top 20)
    imp = get_feature_importance(model, feature_cols)
    log.info("Top 20 features by gain:\n%s", imp.head(20).to_string(index=False))

    return model, history


# ===========================================================================
# STEP 7 — Calibrate on calibration split
# ===========================================================================
def step_calibrate(model, X_calib, y_calib):
    log.info("=" * 60)
    log.info("STEP 7: Probability calibration")
    log.info("=" * 60)

    raw_calib = model.predict(X_calib)
    calibrator = fit_calibrator(raw_calib, y_calib, method=cfg.CALIBRATION_METHOD)
    save_calibrator(calibrator, str(cfg.CALIBRATOR_PATH))

    return calibrator


# ===========================================================================
# STEP 8 — Threshold selection on test set
# ===========================================================================
def step_threshold(calibrator, model, X_test, y_test):
    log.info("=" * 60)
    log.info("STEP 8: Threshold selection")
    log.info("=" * 60)

    raw_test  = model.predict(X_test)
    calib_test = apply_calibration(calibrator, raw_test)

    cost_curve = sweep_thresholds_by_cost(
        calib_test, y_test,
        cost_false_negative=cfg.COST_FALSE_NEGATIVE,
        cost_false_positive=cfg.COST_FALSE_POSITIVE,
    )

    optimal_threshold = find_optimal_threshold(cost_curve)
    log.info("Optimal threshold: %.4f", optimal_threshold)

    # Save cost curve plot
    cfg.ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    plot_path = str(cfg.ARTIFACT_DIR / "cost_curve.png")
    plot_cost_curve(cost_curve, save_path=plot_path)

    return calib_test, optimal_threshold, cost_curve


# ===========================================================================
# STEP 9 — Metrics report
# ===========================================================================
def step_report(calib_test, y_test, threshold):
    log.info("=" * 60)
    log.info("STEP 9: Metrics report")
    log.info("=" * 60)

    report = generate_report(
        calib_test, y_test,
        threshold=threshold,
        cost_false_negative=cfg.COST_FALSE_NEGATIVE,
        cost_false_positive=cfg.COST_FALSE_POSITIVE,
        save_path=str(cfg.ARTIFACT_DIR / "metrics_report.json"),
    )
    return report, threshold


# ===========================================================================
# STEP 10 — PSI drift demo (val vs test as stand-in for reference vs live)
# ===========================================================================
def step_psi_demo(val: pd.DataFrame, test: pd.DataFrame, feature_cols: list[str]):
    log.info("=" * 60)
    log.info("STEP 10: PSI drift demo (val → test)")
    log.info("=" * 60)
    log.info(
        "  Using val split as 'reference' and test split as 'live' "
        "to demonstrate PSI.  In production, reference is captured at "
        "deployment time and live is a rolling window of scored transactions."
    )

    psi_df = psi_report(
        reference_df=val,
        live_df=test,
        feature_cols=feature_cols,
    )
    log.info("PSI report (top 10):\n%s", psi_df.head(10).to_string(index=False))

    # Save reference snapshot for future production use
    save_reference_snapshot(val, feature_cols, str(cfg.REFERENCE_SNAPSHOT_PATH))

    return psi_df


# ===========================================================================
# STEP 11 — Leaf index baseline
# ===========================================================================
def step_leaf_index(model, X_train, y_train):
    log.info("=" * 60)
    log.info("STEP 11: Leaf index baseline")
    log.info("=" * 60)

    # Use a stratified sample of the training set for the reference baseline.
    # Predicting leaf assignments on the full 383k × 1682 trees produces a
    # ~2.5 GB matrix, and computing the modal leaf per row requires another
    # 4.8 GB intermediate array -> OOM.  50k rows gives a stable reference.
    import numpy as np
    rng = np.random.default_rng(42)
    y_arr = np.asarray(y_train)
    fraud_idx  = np.where(y_arr == 1)[0]
    legit_idx  = np.where(y_arr == 0)[0]
    # Preserve class ratio in sample
    n_sample   = min(50_000, len(y_arr))
    fraud_rate = len(fraud_idx) / len(y_arr)
    n_fraud    = min(int(n_sample * fraud_rate) + 1, len(fraud_idx))
    n_legit    = min(n_sample - n_fraud, len(legit_idx))
    sample_idx = np.concatenate([
        rng.choice(fraud_idx, n_fraud,  replace=False),
        rng.choice(legit_idx, n_legit, replace=False),
    ])
    rng.shuffle(sample_idx)

    X_sample = X_train.iloc[sample_idx] if hasattr(X_train, "iloc") else X_train[sample_idx]
    y_sample = y_arr[sample_idx]

    log.info(
        "  Leaf index sample: %d rows (%.0f%% fraud)",
        len(sample_idx), 100 * y_sample.mean(),
    )

    # pred_leaf=True returns shape (n_samples, n_trees).
    # Use tree 0 as the representative leaf per sample — avoids the
    # expensive modal computation while still capturing the key leaf
    # distribution pattern for monitoring purposes.
    leaf_matrix = model.predict(X_sample, pred_leaf=True)  # (n, n_trees)
    leaf_assignments = leaf_matrix[:, 0]                    # first tree only

    leaf_idx = LeafIndex()
    leaf_idx.record_leaf_activations(leaf_assignments, labels=y_sample)
    leaf_idx.set_reference_from_current()

    leaf_index_path = str(cfg.ARTIFACT_DIR / "leaf_index.json")
    leaf_idx.save(leaf_index_path)
    log.info("Leaf index baseline saved to %s", leaf_index_path)
    return leaf_idx


# ===========================================================================
# Main
# ===========================================================================
def main() -> None:
    log.info("=" * 60)
    log.info("  GBT FRAUD DETECTION PIPELINE")
    log.info("=" * 60)

    df                              = step_load()
    train, val, calib, test         = step_split(df)
    train, val, calib, test         = step_features(train, val, calib, test)
    train, val, calib, test, enc    = step_encode(train, val, calib, test)

    (X_train, y_train,
     X_val,   y_val,
     X_calib, y_calib,
     X_test,  y_test,
     feature_cols)                  = step_build_matrices(train, val, calib, test)

    model, history                  = step_train(X_train, y_train, X_val, y_val,
                                                  feature_cols)
    calibrator                      = step_calibrate(model, X_calib, y_calib)
    calib_test, threshold, curve    = step_threshold(calibrator, model,
                                                      X_test, y_test)
    report, threshold               = step_report(calib_test, y_test, threshold)
    psi_df                          = step_psi_demo(val, test, feature_cols)
    leaf_idx                        = step_leaf_index(model, X_train, y_train)

    log.info("=" * 60)
    log.info("  PIPELINE COMPLETE")
    log.info("  Artifacts saved to: %s", cfg.ARTIFACT_DIR)
    log.info("  Optimal threshold : %.4f", threshold)
    log.info("  ROC-AUC           : %.5f", report["roc_auc"])
    log.info("  PR-AUC            : %.5f", report["pr_auc"])
    log.info("=" * 60)


if __name__ == "__main__":
    main()

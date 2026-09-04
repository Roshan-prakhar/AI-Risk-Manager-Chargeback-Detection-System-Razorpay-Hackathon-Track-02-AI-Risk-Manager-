"""
run_leaf_index_only.py
----------------------
Re-runs ONLY step 11 (leaf index baseline) loading the already-saved model
and train split artifacts.  Run this after the main pipeline completed steps
1-10 successfully.
"""
import logging
import sys
import numpy as np
import joblib
import lightgbm as lgb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("leaf_rerun")

from fraud_gbt import config as cfg
from fraud_gbt.monitoring.leaf_index import LeafIndex

# ---- Load model ----
log.info("Loading model from %s", cfg.MODEL_PATH)
model = lgb.Booster(model_file=str(cfg.MODEL_PATH))
log.info("Model loaded: %d trees", model.num_trees())

# ---- Load encoder + train stats (need to rebuild X_train) ----
log.info("Loading saved artifacts to reconstruct train split...")
from fraud_gbt.data.loader import load_transactions, load_identity, merge_identity
from fraud_gbt.data.time_split import time_based_split
from fraud_gbt.features.build_features import build_all_features
from fraud_gbt.features.encoders import apply_categorical_encoder
import pandas as pd

tx       = load_transactions(str(cfg.TRANSACTION_CSV), dtype_map=cfg.DTYPE_MAP)
identity = load_identity(str(cfg.IDENTITY_CSV))
df       = merge_identity(tx, identity, join_key=cfg.ID_COL)
df       = df.drop(columns=[cfg.ID_COL], errors="ignore")

train, _, _, _ = time_based_split(df, dt_col=cfg.TIME_COL,
                                   train_frac=cfg.TRAIN_FRAC,
                                   val_frac=cfg.VAL_FRAC,
                                   calib_frac=cfg.CALIB_FRAC)

stats       = joblib.load(cfg.TRAIN_STATS_PATH)
encoder_map = joblib.load(cfg.ENCODER_PATH)

train = build_all_features(train,
                            card_stats=stats["card_stats"],
                            global_mean=stats["global_mean"],
                            global_std=stats["global_std"],
                            card_freq=stats["card_freq"],
                            missingness_cols=cfg.MISSINGNESS_FLAG_COLS)
train = apply_categorical_encoder(train, encoder_map)

exclude      = {cfg.LABEL_COL, cfg.TIME_COL}
feature_cols = [c for c in train.columns
                if c not in exclude and pd.api.types.is_numeric_dtype(train[c])]
log.info("Feature cols: %d", len(feature_cols))

X_train = train[feature_cols]
y_train = train[cfg.LABEL_COL].values

# ---- Leaf index (sampled, tree-0) ----
log.info("=" * 60)
log.info("STEP 11: Leaf index baseline")
log.info("=" * 60)

rng       = np.random.default_rng(42)
y_arr     = np.asarray(y_train)
fraud_idx = np.where(y_arr == 1)[0]
legit_idx = np.where(y_arr == 0)[0]
n_sample  = min(50_000, len(y_arr))
fraud_rate = len(fraud_idx) / len(y_arr)
n_fraud   = min(int(n_sample * fraud_rate) + 1, len(fraud_idx))
n_legit   = min(n_sample - n_fraud, len(legit_idx))
sample_idx = np.concatenate([
    rng.choice(fraud_idx, n_fraud,  replace=False),
    rng.choice(legit_idx, n_legit, replace=False),
])
rng.shuffle(sample_idx)

X_sample = X_train.iloc[sample_idx]
y_sample = y_arr[sample_idx]
log.info("Sample: %d rows (%.1f%% fraud)", len(sample_idx), 100 * y_sample.mean())

leaf_matrix      = model.predict(X_sample, pred_leaf=True)
leaf_assignments = leaf_matrix[:, 0]   # tree-0 leaf IDs

leaf_idx = LeafIndex()
leaf_idx.record_leaf_activations(leaf_assignments, labels=y_sample)
leaf_idx.set_reference_from_current()

out_path = str(cfg.ARTIFACT_DIR / "leaf_index.json")
leaf_idx.save(out_path)
log.info("=" * 60)
log.info("Leaf index baseline saved to %s", out_path)
suspicious = leaf_idx.get_suspicious_leaves()
log.info("Suspicious leaves at baseline: %d (expected 0)", len(suspicious))
log.info("STEP 11: COMPLETE")
log.info("=" * 60)

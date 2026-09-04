"""
config.py
---------
Central registry for paths, feature lists, thresholds, cost-matrix values,
and split fractions.  Every other module imports from here; no magic numbers
in individual modules.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project root & artifact directories
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent          # GBT-Classifier-Model/
DATA_DIR     = Path(r"C:\Users\BIT\Downloads\ieee-fraud-detection")
ARTIFACT_DIR = PROJECT_ROOT / "artifacts"            # saved models, calibrators
LOG_DIR      = PROJECT_ROOT / "logs"

# ---------------------------------------------------------------------------
# Raw data paths
# ---------------------------------------------------------------------------
TRANSACTION_CSV      = DATA_DIR / "train_transaction.csv"
IDENTITY_CSV         = DATA_DIR / "train_identity.csv"
TEST_TRANSACTION_CSV = DATA_DIR / "test_transaction.csv"
TEST_IDENTITY_CSV    = DATA_DIR / "test_identity.csv"
SAMPLE_SUBMISSION    = DATA_DIR / "sample_submission.csv"

# ---------------------------------------------------------------------------
# Artifact paths
# ---------------------------------------------------------------------------
MODEL_PATH      = ARTIFACT_DIR / "gbt_model.txt"
CALIBRATOR_PATH = ARTIFACT_DIR / "calibrator.joblib"
ENCODER_PATH    = ARTIFACT_DIR / "cat_encoder.joblib"
TRAIN_STATS_PATH= ARTIFACT_DIR / "train_stats.joblib"   # mean/std per card
FEATURE_COLS_PATH = ARTIFACT_DIR / "feature_cols.joblib" # ordered feature list
REFERENCE_SNAPSHOT_PATH = ARTIFACT_DIR / "psi_reference.joblib"
PERF_TRACKER_LOG = LOG_DIR / "performance_tracker.json"

# ---------------------------------------------------------------------------
# Label column
# ---------------------------------------------------------------------------
LABEL_COL = "isFraud"
ID_COL    = "TransactionID"
TIME_COL  = "TransactionDT"

# ---------------------------------------------------------------------------
# Columns to drop before modelling
# (keep TransactionID only for joining; drop after merge)
# ---------------------------------------------------------------------------
DROP_COLS = [ID_COL]

# ---------------------------------------------------------------------------
# Explicit dtype map  (memory-safe; avoids 2× float64 default cost)
# ---------------------------------------------------------------------------
DTYPE_MAP: dict = {
    "TransactionID":  "int32",
    "isFraud":        "int8",
    "TransactionDT":  "int32",
    "TransactionAmt": "float32",
    "ProductCD":      "category",
    "card1":          "int16",
    "card2":          "float32",
    "card3":          "float32",
    "card4":          "category",
    "card5":          "float32",
    "card6":          "category",
    "addr1":          "float32",
    "addr2":          "float32",
    "dist1":          "float32",
    "dist2":          "float32",
    "P_emaildomain":  "category",
    "R_emaildomain":  "category",
}
# Remaining C/D/V/M columns are read as float32 via read_csv low_memory=False

# ---------------------------------------------------------------------------
# Categorical columns  (fit encoder on train only)
# ---------------------------------------------------------------------------
CAT_COLS = [
    # Transaction table
    "ProductCD", "card4", "card6", "P_emaildomain", "R_emaildomain",
    "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9",
    # Identity table — string-typed categoricals
    "DeviceType", "DeviceInfo",
    "id_12", "id_15", "id_16", "id_23", "id_27", "id_28", "id_29",
    "id_30", "id_31", "id_33", "id_34", "id_35", "id_36", "id_37", "id_38",
]

# ---------------------------------------------------------------------------
# Missingness flags  (null is informative for these columns)
# ---------------------------------------------------------------------------
MISSINGNESS_FLAG_COLS = ["dist1", "P_emaildomain", "addr1", "dist2"]

# ---------------------------------------------------------------------------
# Time-based split fractions  (must sum to 1.0)
# ---------------------------------------------------------------------------
TRAIN_FRAC = 0.65
VAL_FRAC   = 0.15
CALIB_FRAC = 0.10
TEST_FRAC  = 0.10     # derived as 1 - TRAIN_FRAC - VAL_FRAC - CALIB_FRAC

# ---------------------------------------------------------------------------
# Cost matrix  (relative units; tune to your business case)
# ---------------------------------------------------------------------------
COST_FALSE_NEGATIVE = 10.0   # missed fraud — lost transaction value
COST_FALSE_POSITIVE =  1.0   # false alarm — customer friction / review cost

# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------
CALIBRATION_METHOD = "platt"   # "platt" | "isotonic"

# ---------------------------------------------------------------------------
# Monitoring thresholds
# ---------------------------------------------------------------------------
PSI_STABLE   = 0.10
PSI_MONITOR  = 0.25

ROLLING_RECALL_ALERT_DELTA = 0.05   # alert if recall drops > 5pp from baseline
ROLLING_FPR_ALERT_DELTA    = 0.02   # alert if FPR rises  > 2pp from baseline
ROLLING_WINDOW_DAYS        = 7

# ---------------------------------------------------------------------------
# Recurrence validation gate
# ---------------------------------------------------------------------------
MIN_RECURRENCE_LIFT = 1.5   # only build recurrence feature if lift exceeds this

# ---------------------------------------------------------------------------
# LightGBM hyper-parameters
# ---------------------------------------------------------------------------
LGB_PARAMS = {
    "objective":          "binary",
    "metric":             "auc",
    "learning_rate":      0.01,
    "num_leaves":         31,
    "min_child_samples":  100,
    "reg_lambda":         1.0,
    "reg_alpha":          0.5,
    "feature_fraction":   0.8,
    "bagging_fraction":   0.8,
    "bagging_freq":       5,
    "verbose":            -1,
    "n_jobs":             -1,
    "seed":               42,
}
LGB_N_ESTIMATORS       = 2000
LGB_EARLY_STOPPING     = 50

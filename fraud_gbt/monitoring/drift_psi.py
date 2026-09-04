"""
monitoring/drift_psi.py
-----------------------
Population Stability Index (PSI) for feature and score drift monitoring.

Design notes
------------
PSI compares the distribution of live feature/score values against a fixed
reference snapshot captured at model deployment.

Industry rule of thumb:
  PSI < 0.10  : stable
  0.10–0.25   : worth watching / monitor
  > 0.25      : real shift — investigate or consider retraining

Why PSI instead of just re-evaluating metrics?
PSI does NOT require ground-truth labels.  Fraud labels arrive with a delay
(chargeback window, dispute resolution).  PSI flags a changing world *before*
you'd notice via degraded recall weeks later.  It is the natural external
complement to the leaf monitoring index (drift_psi watches the inputs; the
leaf index watches internal model components).

Implementation detail: bin edges must be shared and derived from the
*reference* distribution's quantiles.  Applying reference edges to the live
distribution reveals distributional shift; using separate bin edges per
window would mask it.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

PSI_STABLE  = 0.10
PSI_MONITOR = 0.25

_EPSILON = 1e-8  # small constant to prevent log(0)


def compute_psi(
    reference: np.ndarray,
    live: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Compute the Population Stability Index between two distributions.

    Parameters
    ----------
    reference : np.ndarray
        Distribution captured at model deployment (reference window).
    live : np.ndarray
        Current / live distribution to compare against the reference.
    n_bins : int
        Number of bins.  Bin edges are derived from *reference* quantiles
        so both distributions use the same boundaries.

    Returns
    -------
    float
        PSI value.  0.0 when distributions are identical.

    Notes
    -----
    PSI = Σ (live_% - ref_%) × ln(live_% / ref_%)

    A PSI of 0.0 means the two distributions are identical.
    Results are only meaningful when both arrays have a reasonable number
    of observations (n ≥ 100 recommended per bin on average).
    """
    ref  = np.asarray(reference, dtype=float)
    live_ = np.asarray(live, dtype=float)

    if len(ref) == 0 or len(live_) == 0:
        raise ValueError("reference and live arrays must be non-empty.")

    # Derive bin edges from reference quantiles
    quantiles = np.linspace(0, 100, n_bins + 1)
    bin_edges = np.unique(np.percentile(ref, quantiles))

    # Edge case: all reference values are identical
    if len(bin_edges) < 2:
        log.warning(
            "compute_psi: reference distribution has no variance "
            "(all values identical).  PSI cannot be computed meaningfully; "
            "returning 0.0."
        )
        return 0.0

    # Extend edges to catch all live values
    bin_edges[0]  = -np.inf
    bin_edges[-1] = np.inf

    ref_counts,  _ = np.histogram(ref,   bins=bin_edges)
    live_counts, _ = np.histogram(live_, bins=bin_edges)

    ref_pct  = (ref_counts  + _EPSILON) / (len(ref)   + _EPSILON * len(ref_counts))
    live_pct = (live_counts + _EPSILON) / (len(live_) + _EPSILON * len(live_counts))

    psi = float(np.sum((live_pct - ref_pct) * np.log(live_pct / ref_pct)))
    return psi


def psi_status(psi_value: float) -> str:
    """Translate a PSI value into a human-readable status label."""
    if psi_value < PSI_STABLE:
        return "STABLE"
    elif psi_value < PSI_MONITOR:
        return "MONITOR"
    else:
        return "INVESTIGATE"


def psi_report(
    reference_df: pd.DataFrame,
    live_df: pd.DataFrame,
    feature_cols: list[str],
    n_bins: int = 10,
) -> pd.DataFrame:
    """Compute per-feature PSI across the full feature set.

    Run this on a schedule against a rolling window of live scored
    transactions, comparing to the reference snapshot taken at deployment.

    Parameters
    ----------
    reference_df : pd.DataFrame
        Reference snapshot (e.g. training or a deployment-time window).
    live_df : pd.DataFrame
        Live / current window of scored transactions.
    feature_cols : list[str]
        Features to evaluate.  Columns not present in either DataFrame
        are skipped with a warning.
    n_bins : int

    Returns
    -------
    pd.DataFrame
        Columns: ``[feature, psi, status]``, sorted by PSI descending.
        Rows with status INVESTIGATE are the most urgent to act on.
    """
    records = []
    for col in feature_cols:
        if col not in reference_df.columns:
            log.warning("psi_report: '%s' not in reference_df; skipping.", col)
            continue
        if col not in live_df.columns:
            log.warning("psi_report: '%s' not in live_df; skipping.", col)
            continue

        ref_vals  = reference_df[col].dropna().values
        live_vals = live_df[col].dropna().values

        if len(ref_vals) < 2 or len(live_vals) < 2:
            log.warning("psi_report: '%s' has too few non-null values; skipping.", col)
            continue

        try:
            psi_val = compute_psi(ref_vals, live_vals, n_bins=n_bins)
        except Exception as exc:
            log.warning("psi_report: error computing PSI for '%s': %s", col, exc)
            continue

        records.append({
            "feature": col,
            "psi":     round(psi_val, 5),
            "status":  psi_status(psi_val),
        })

    if not records:
        return pd.DataFrame(columns=["feature", "psi", "status"])

    result = (
        pd.DataFrame(records)
        .sort_values("psi", ascending=False)
        .reset_index(drop=True)
    )

    n_investigate = (result["status"] == "INVESTIGATE").sum()
    n_monitor     = (result["status"] == "MONITOR").sum()
    log.info(
        "PSI report: %d features evaluated — "
        "%d INVESTIGATE, %d MONITOR, %d STABLE.",
        len(result), n_investigate, n_monitor,
        len(result) - n_investigate - n_monitor,
    )

    return result


# ---------------------------------------------------------------------------
# Reference snapshot persistence
# ---------------------------------------------------------------------------

def save_reference_snapshot(
    df: pd.DataFrame,
    feature_cols: list[str],
    path: str,
) -> None:
    """Save a reference distribution snapshot to disk.

    Parameters
    ----------
    df : pd.DataFrame
        The reference window (e.g. training data at deployment time).
    feature_cols : list[str]
        Features to include in the snapshot.
    path : str
        Destination file path (joblib format).
    """
    snapshot = {col: df[col].dropna().values for col in feature_cols
                if col in df.columns}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(snapshot, path)
    log.info("PSI reference snapshot saved to %s (%d features).", path, len(snapshot))


def load_reference_snapshot(path: str) -> dict[str, np.ndarray]:
    """Load a reference distribution snapshot from disk."""
    snapshot = joblib.load(path)
    log.info("PSI reference snapshot loaded from %s.", path)
    return snapshot

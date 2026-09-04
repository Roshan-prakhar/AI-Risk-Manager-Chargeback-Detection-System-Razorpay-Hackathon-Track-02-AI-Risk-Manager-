"""
evaluation/threshold_selection.py
----------------------------------
Cost-matrix threshold sweep over calibrated probabilities.

Design note
-----------
Always return the *full cost curve*, not just the argmin.  A single optimal
threshold number invites the question "why this exact threshold?" with no
visual answer.  Callers should plot/report the full curve alongside the
chosen point.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

log = logging.getLogger(__name__)


def sweep_thresholds_by_cost(
    calibrated_probs: np.ndarray,
    y_true: np.ndarray,
    cost_false_negative: float,
    cost_false_positive: float,
    thresholds: np.ndarray | None = None,
) -> pd.DataFrame:
    """Sweep classification thresholds and return the full cost curve.

    Parameters
    ----------
    calibrated_probs : np.ndarray, shape (n,)
        Calibrated model probabilities (output of ``apply_calibration``).
        Must be on the **test** split only.
    y_true : np.ndarray, shape (n,)
        True fraud labels.
    cost_false_negative : float
        Business cost of a missed fraud (false negative).  In relative
        units; ratio to cost_false_positive is what matters.
    cost_false_positive : float
        Business cost of a false alarm (false positive / incorrect flag).
    thresholds : np.ndarray, optional
        Array of thresholds to evaluate.  Defaults to
        ``np.arange(0.01, 0.99, 0.01)``.

    Returns
    -------
    pd.DataFrame
        One row per threshold, columns:
        ``[threshold, cost, precision, recall, f1, TP, FP, TN, FN]``
        Sorted by threshold ascending.
        The optimal (minimum-cost) row is logged.

    Notes
    -----
    ``cost = FN * cost_false_negative + FP * cost_false_positive``

    This is the raw count-weighted cost, not per-transaction normalised.
    Normalise as needed for your business reporting.
    """
    if thresholds is None:
        thresholds = np.arange(0.01, 0.99, 0.01)

    probs = np.asarray(calibrated_probs, dtype=float)
    y     = np.asarray(y_true, dtype=int)

    records = []
    for thresh in thresholds:
        preds = (probs >= thresh).astype(int)
        tn, fp, fn, tp = confusion_matrix(y, preds, labels=[0, 1]).ravel()

        cost = fn * cost_false_negative + fp * cost_false_positive

        prec  = precision_score(y, preds, zero_division=0)
        rec   = recall_score(y, preds, zero_division=0)
        f1    = f1_score(y, preds, zero_division=0)

        records.append({
            "threshold": round(float(thresh), 4),
            "cost":      float(cost),
            "precision": float(prec),
            "recall":    float(rec),
            "f1":        float(f1),
            "TP":        int(tp),
            "FP":        int(fp),
            "TN":        int(tn),
            "FN":        int(fn),
        })

    result = pd.DataFrame(records).sort_values("threshold").reset_index(drop=True)

    best = result.loc[result["cost"].idxmin()]
    log.info(
        "Optimal threshold: %.2f  "
        "(cost=%.1f, precision=%.3f, recall=%.3f, F1=%.3f, "
        "TP=%d, FP=%d, FN=%d)",
        best["threshold"], best["cost"],
        best["precision"], best["recall"], best["f1"],
        best["TP"], best["FP"], best["FN"],
    )

    return result


def find_optimal_threshold(cost_curve: pd.DataFrame) -> float:
    """Return the threshold with the minimum total cost.

    Parameters
    ----------
    cost_curve : pd.DataFrame
        Output of ``sweep_thresholds_by_cost``.

    Returns
    -------
    float
        Threshold value at minimum cost.
    """
    return float(cost_curve.loc[cost_curve["cost"].idxmin(), "threshold"])


def plot_cost_curve(
    cost_curve: pd.DataFrame,
    save_path: str | None = None,
) -> None:
    """Plot the cost curve with the optimal threshold marked.

    Parameters
    ----------
    cost_curve : pd.DataFrame
        Output of ``sweep_thresholds_by_cost``.
    save_path : str, optional
        If provided, saves the figure to this path instead of displaying.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        log.warning("matplotlib not available; skipping cost-curve plot.")
        return

    opt_thresh = find_optimal_threshold(cost_curve)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # Cost curve
    ax = axes[0]
    ax.plot(cost_curve["threshold"], cost_curve["cost"], color="steelblue", lw=2)
    ax.axvline(opt_thresh, color="crimson", linestyle="--",
               label=f"Optimal = {opt_thresh:.2f}")
    ax.set_xlabel("Threshold")
    ax.set_ylabel("Total Cost (FN×C_fn + FP×C_fp)")
    ax.set_title("Cost Curve")
    ax.legend()

    # Precision / Recall / F1 vs threshold
    ax2 = axes[1]
    ax2.plot(cost_curve["threshold"], cost_curve["precision"],
             label="Precision", lw=2)
    ax2.plot(cost_curve["threshold"], cost_curve["recall"],
             label="Recall", lw=2)
    ax2.plot(cost_curve["threshold"], cost_curve["f1"],
             label="F1", lw=2, linestyle="--")
    ax2.axvline(opt_thresh, color="crimson", linestyle="--",
                label=f"Optimal = {opt_thresh:.2f}")
    ax2.set_xlabel("Threshold")
    ax2.set_ylabel("Score")
    ax2.set_title("Precision / Recall / F1 vs Threshold")
    ax2.legend()

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        log.info("Cost curve saved to %s", save_path)
    else:
        plt.show()

    plt.close(fig)

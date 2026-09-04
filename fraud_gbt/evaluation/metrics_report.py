"""
evaluation/metrics_report.py
-----------------------------
Full classification report, ROC-AUC, and cost summary on the held-out test set.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)

log = logging.getLogger(__name__)


def generate_report(
    calibrated_probs: np.ndarray,
    y_true: np.ndarray,
    threshold: float,
    cost_false_negative: float,
    cost_false_positive: float,
    save_path: str | None = None,
) -> dict:
    """Compute and print a full evaluation report on the test set.

    Parameters
    ----------
    calibrated_probs : np.ndarray
        Calibrated model probabilities on the **test** split.
    y_true : np.ndarray
        True fraud labels for the test split.
    threshold : float
        Decision threshold (from cost-curve optimisation).
    cost_false_negative, cost_false_positive : float
        Cost matrix values for total-cost computation.
    save_path : str, optional
        If provided, save the report dict as a JSON file here.

    Returns
    -------
    dict
        Report dictionary with all metrics.
    """
    probs = np.asarray(calibrated_probs, dtype=float)
    y     = np.asarray(y_true, dtype=int)
    preds = (probs >= threshold).astype(int)

    roc_auc  = roc_auc_score(y, probs)
    pr_auc   = average_precision_score(y, probs)
    tn, fp, fn, tp = confusion_matrix(y, preds, labels=[0, 1]).ravel()
    total_cost = fn * cost_false_negative + fp * cost_false_positive

    clf_report = classification_report(y, preds, target_names=["Legit", "Fraud"],
                                       output_dict=True, zero_division=0)

    report = {
        "threshold":        threshold,
        "roc_auc":          round(float(roc_auc), 5),
        "pr_auc":           round(float(pr_auc), 5),
        "total_cost":       round(float(total_cost), 2),
        "cost_fn":          cost_false_negative,
        "cost_fp":          cost_false_positive,
        "TP":               int(tp),
        "FP":               int(fp),
        "TN":               int(tn),
        "FN":               int(fn),
        "classification_report": clf_report,
    }

    _print_report(report)

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as f:
            json.dump(report, f, indent=2)
        log.info("Metrics report saved to %s", save_path)

    return report


def _print_report(report: dict) -> None:
    """Print a formatted summary to stdout."""
    sep = "=" * 60
    print(sep)
    print("  FRAUD DETECTION — TEST SET EVALUATION REPORT")
    print(sep)
    print(f"  Threshold (cost-optimised) : {report['threshold']:.4f}")
    print(f"  ROC-AUC                    : {report['roc_auc']:.5f}")
    print(f"  PR-AUC                     : {report['pr_auc']:.5f}")
    print(sep)
    print(f"  Confusion Matrix")
    print(f"    True Positives  (TP) : {report['TP']:>8,}")
    print(f"    False Positives (FP) : {report['FP']:>8,}  ← false alarms")
    print(f"    True Negatives  (TN) : {report['TN']:>8,}")
    print(f"    False Negatives (FN) : {report['FN']:>8,}  ← missed fraud")
    print(sep)
    cr = report["classification_report"]
    fraud = cr.get("Fraud", {})
    print(f"  Fraud class")
    print(f"    Precision : {fraud.get('precision', 0):.4f}")
    print(f"    Recall    : {fraud.get('recall', 0):.4f}")
    print(f"    F1        : {fraud.get('f1-score', 0):.4f}")
    print(sep)
    print(
        f"  Total Cost : {report['total_cost']:,.2f}  "
        f"(FN×{report['cost_fn']:.1f} + FP×{report['cost_fp']:.1f})"
    )
    print(sep)

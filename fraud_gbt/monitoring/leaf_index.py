"""
monitoring/leaf_index.py
------------------------
Per-leaf firing and outcome tracking.

Design notes
------------
The leaf monitoring index watches *internal model components* for known
failure patterns: leaves that are firing much more frequently than at
training time, or whose fraud-outcome rate has shifted.  This is the
internal complement to PSI-based drift monitoring (drift_psi.py), which
watches the *input feature distributions* from the outside.

Together they cover both failure modes:
  - drift_psi  → inputs are changing (world changed)
  - leaf_index → internal components behaving differently (model failing)
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def _fast_row_mode(arr: np.ndarray) -> np.ndarray:
    """Return the modal (most frequent) value per row using numpy.

    Replaces scipy.stats.mode which is prohibitively slow on large 2-D arrays
    (e.g. 383k rows x 1682 trees takes many minutes; this runs in seconds).

    Parameters
    ----------
    arr : np.ndarray, shape (n_samples, n_trees)

    Returns
    -------
    np.ndarray, shape (n_samples,)
        Modal leaf index per sample.
    """
    n_rows = arr.shape[0]
    result = np.empty(n_rows, dtype=arr.dtype)
    for i in range(n_rows):
        row = arr[i]
        vals, counts = np.unique(row, return_counts=True)
        result[i] = vals[np.argmax(counts)]
    return result


class LeafIndex:
    """Track per-leaf firing counts and fraud-outcome rates.

    Attributes
    ----------
    leaf_counts : dict[int, int]
        Total number of transactions assigned to each leaf.
    leaf_fraud_counts : dict[int, int]
        Number of confirmed fraud transactions per leaf.
    reference_counts : dict[int, int]
        Leaf counts from the reference/training snapshot.
    reference_fraud_rates : dict[int, float]
        Per-leaf fraud rates from the reference/training snapshot.
    """

    def __init__(self) -> None:
        self.leaf_counts:       dict[int, int]   = defaultdict(int)
        self.leaf_fraud_counts: dict[int, int]   = defaultdict(int)
        self.reference_counts:      dict[int, int]   = {}
        self.reference_fraud_rates: dict[int, float] = {}

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_leaf_activations(
        self,
        leaf_assignments: np.ndarray,
        labels: Optional[np.ndarray] = None,
    ) -> None:
        """Update per-leaf counters from a batch of transactions.

        Parameters
        ----------
        leaf_assignments : np.ndarray, shape (n_samples,) or (n_samples, n_trees)
            Leaf indices from ``model.predict(X, pred_leaf=True)``.
            If 2-D (one leaf per tree per sample), uses the majority-leaf
            heuristic: the most-frequent leaf across trees per sample.
        labels : np.ndarray, shape (n_samples,), optional
            Resolved fraud labels (1 = fraud, 0 = legit).  If provided,
            updates the fraud-count index.  Pass None for unresolved
            transactions.
        """
        arr = np.asarray(leaf_assignments)
        if arr.ndim == 2:
            # Summarise multi-tree leaf assignments: fast numpy modal leaf per sample.
            # scipy.stats.mode on a (383k, 1682) matrix is prohibitively slow;
            # numpy bincount is pure C and ~100x faster.
            arr = _fast_row_mode(arr)

        arr = arr.ravel().astype(int)

        for i, leaf in enumerate(arr):
            self.leaf_counts[leaf] += 1
            if labels is not None:
                self.leaf_fraud_counts[leaf] += int(labels[i])

    def set_reference_from_current(self) -> None:
        """Snapshot current state as the reference baseline.

        Call this once after processing the training set to establish the
        expected leaf distribution.
        """
        self.reference_counts = dict(self.leaf_counts)
        total = sum(self.reference_counts.values()) or 1
        self.reference_fraud_rates = {
            leaf: self.leaf_fraud_counts.get(leaf, 0) / max(cnt, 1)
            for leaf, cnt in self.reference_counts.items()
        }
        log.info(
            "Leaf index reference set: %d unique leaves, "
            "%d total activations.",
            len(self.reference_counts), total,
        )

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def get_suspicious_leaves(
        self,
        activation_ratio_threshold: float = 2.0,
        fraud_rate_delta_threshold: float = 0.10,
        min_activations: int = 10,
    ) -> pd.DataFrame:
        """Return leaves with anomalous activation counts or outcome shifts.

        Parameters
        ----------
        activation_ratio_threshold : float
            Flag a leaf if live_count / reference_count exceeds this ratio.
            Default 2.0 (firing twice as often as at training).
        fraud_rate_delta_threshold : float
            Flag a leaf if |live_fraud_rate - reference_fraud_rate| exceeds
            this delta.  Default 0.10 (10 pp shift).
        min_activations : int
            Minimum total live activations before a leaf is evaluated.

        Returns
        -------
        pd.DataFrame
            Columns: ``[leaf_id, live_count, ref_count, activation_ratio,
            live_fraud_rate, ref_fraud_rate, fraud_rate_delta, flags]``
            Sorted by ``activation_ratio`` descending.
        """
        if not self.reference_counts:
            raise RuntimeError(
                "Reference snapshot is empty. "
                "Call set_reference_from_current() first."
            )

        records = []
        all_leaves = set(self.leaf_counts) | set(self.reference_counts)

        for leaf in all_leaves:
            live_count = self.leaf_counts.get(leaf, 0)
            ref_count  = self.reference_counts.get(leaf, 0)

            if live_count < min_activations:
                continue

            act_ratio = live_count / max(ref_count, 1)
            live_fraud_rate = (
                self.leaf_fraud_counts.get(leaf, 0) / max(live_count, 1)
            )
            ref_fraud_rate = self.reference_fraud_rates.get(leaf, 0.0)
            fraud_delta = abs(live_fraud_rate - ref_fraud_rate)

            flags = []
            if act_ratio >= activation_ratio_threshold:
                flags.append("HIGH_ACTIVATION")
            if fraud_delta >= fraud_rate_delta_threshold:
                flags.append("FRAUD_RATE_SHIFT")

            if flags:
                records.append({
                    "leaf_id":          leaf,
                    "live_count":       live_count,
                    "ref_count":        ref_count,
                    "activation_ratio": round(act_ratio, 3),
                    "live_fraud_rate":  round(live_fraud_rate, 4),
                    "ref_fraud_rate":   round(ref_fraud_rate, 4),
                    "fraud_rate_delta": round(fraud_delta, 4),
                    "flags":            "|".join(flags),
                })

        df = pd.DataFrame(records)
        if not df.empty:
            df = df.sort_values("activation_ratio", ascending=False).reset_index(
                drop=True
            )
            log.info(
                "Suspicious leaves: %d flagged (HIGH_ACTIVATION or FRAUD_RATE_SHIFT).",
                len(df),
            )
        else:
            log.info("Leaf index: no suspicious leaves detected.")

        return df

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Persist the full index state to a JSON file."""
        # Convert numpy int64 keys to native Python int — json.dump only
        # accepts str/int/float/bool/None as dict keys, not numpy integers.
        def _to_int_keys(d: dict) -> dict:
            return {int(k): v for k, v in d.items()}

        state = {
            "leaf_counts":           _to_int_keys(dict(self.leaf_counts)),
            "leaf_fraud_counts":     _to_int_keys(dict(self.leaf_fraud_counts)),
            "reference_counts":      _to_int_keys(dict(self.reference_counts)),
            "reference_fraud_rates": _to_int_keys(dict(self.reference_fraud_rates)),
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
        log.info("LeafIndex saved to %s", path)

    @classmethod
    def load(cls, path: str) -> "LeafIndex":
        """Load a persisted LeafIndex from a JSON file."""
        with open(path) as f:
            state = json.load(f)
        idx = cls()
        idx.leaf_counts       = defaultdict(int, {int(k): v for k, v in
                                                   state["leaf_counts"].items()})
        idx.leaf_fraud_counts = defaultdict(int, {int(k): v for k, v in
                                                   state["leaf_fraud_counts"].items()})
        idx.reference_counts      = {int(k): v for k, v in
                                      state["reference_counts"].items()}
        idx.reference_fraud_rates = {int(k): v for k, v in
                                      state["reference_fraud_rates"].items()}
        log.info("LeafIndex loaded from %s", path)
        return idx

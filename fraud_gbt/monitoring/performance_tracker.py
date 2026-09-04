"""
monitoring/performance_tracker.py
----------------------------------
Rolling recall and false-positive-rate tracker for delayed-label evaluation.

Design notes
------------
Real fraud labels arrive with a delay (chargeback window, dispute resolution).
This tracker is called once per dispute resolution and maintains a rolling
performance log.  It alerts when recall drops or FPR rises past a set delta
from the release baseline — the delayed-label equivalent of a real-time
dashboard.

This is what actually answers "how do you know this keeps working after
deployment?" given that standard metric evaluation requires labels that don't
exist yet.

State is persisted to a JSON log file so the tracker survives restarts.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_DEFAULT_LOG = "logs/performance_tracker.json"


class PerformanceTracker:
    """Rolling recall / FPR tracker fed by resolved dispute labels.

    Attributes
    ----------
    baseline_recall : float
        Recall at model release (set once via ``set_baseline``).
    baseline_fpr : float
        FPR at model release (set once via ``set_baseline``).
    recall_alert_delta : float
        Alert if recall drops more than this below baseline.
    fpr_alert_delta : float
        Alert if FPR rises more than this above baseline.
    rolling_window_days : int
        How many days of resolved labels to include in rolling metrics.
    log_path : str
        Path to the JSON persistence file.
    """

    def __init__(
        self,
        log_path: str = _DEFAULT_LOG,
        baseline_recall: float = 0.0,
        baseline_fpr: float = 0.0,
        recall_alert_delta: float = 0.05,
        fpr_alert_delta: float = 0.02,
        rolling_window_days: int = 7,
    ) -> None:
        self.log_path            = log_path
        self.baseline_recall     = baseline_recall
        self.baseline_fpr        = baseline_fpr
        self.recall_alert_delta  = recall_alert_delta
        self.fpr_alert_delta     = fpr_alert_delta
        self.rolling_window_days = rolling_window_days

        # In-memory log: list of resolved-label records
        self._records: list[dict] = []
        self._load_existing_log()

    # ------------------------------------------------------------------
    # Baseline
    # ------------------------------------------------------------------

    def set_baseline(self, recall: float, fpr: float) -> None:
        """Set the release-time baseline metrics.

        Parameters
        ----------
        recall : float
            Recall on the held-out test set at deployment.
        fpr : float
            False-positive rate on the held-out test set at deployment.
        """
        self.baseline_recall = recall
        self.baseline_fpr    = fpr
        log.info(
            "Baseline set: recall=%.4f, FPR=%.4f", recall, fpr
        )

    # ------------------------------------------------------------------
    # Label resolution update
    # ------------------------------------------------------------------

    def update_on_resolved_label(
        self,
        transaction_id: str | int,
        predicted_label: int,
        actual_label: int,
        resolved_at: datetime | None = None,
    ) -> None:
        """Record an outcome once a dispute resolves.

        Called when a chargeback resolves or the hold window expires clean.
        Feeds the rolling recall / FPR tracker and triggers an alert if
        either metric has shifted past the configured delta from baseline.

        Parameters
        ----------
        transaction_id : str | int
            Transaction identifier (for audit trail).
        predicted_label : int
            Model's binary prediction (0 or 1) at the time of scoring.
        actual_label : int
            Ground-truth label (1 = confirmed fraud, 0 = legitimate).
        resolved_at : datetime, optional
            When the dispute resolved.  Defaults to now (UTC).
        """
        if resolved_at is None:
            resolved_at = datetime.now(tz=timezone.utc)

        record = {
            "transaction_id":  str(transaction_id),
            "predicted":       int(predicted_label),
            "actual":          int(actual_label),
            "resolved_at":     resolved_at.isoformat(),
        }
        self._records.append(record)
        self._persist()

        # Re-evaluate rolling metrics and check for alerts
        metrics = self.get_rolling_metrics()
        if metrics is None:
            return

        recall = metrics["recall"]
        fpr    = metrics["fpr"]
        window = metrics["window_records"]

        if self.baseline_recall > 0:
            recall_drop = self.baseline_recall - recall
            if recall_drop > self.recall_alert_delta:
                log.warning(
                    "[ALERT] RECALL ALERT: rolling recall=%.4f has dropped %.4f pp "
                    "from baseline=%.4f (threshold=%.4f, window=%d records).",
                    recall, recall_drop, self.baseline_recall,
                    self.recall_alert_delta, window,
                )

        if self.baseline_fpr > 0:
            fpr_rise = fpr - self.baseline_fpr
            if fpr_rise > self.fpr_alert_delta:
                log.warning(
                    "[ALERT] FPR ALERT: rolling FPR=%.4f has risen %.4f pp "
                    "from baseline=%.4f (threshold=%.4f, window=%d records).",
                    fpr, fpr_rise, self.baseline_fpr,
                    self.fpr_alert_delta, window,
                )

    # ------------------------------------------------------------------
    # Rolling metrics
    # ------------------------------------------------------------------

    def get_rolling_metrics(self) -> dict | None:
        """Compute recall and FPR over the rolling window.

        Returns
        -------
        dict or None
            Keys: ``{recall, fpr, window_records, window_days,
            TP, FP, TN, FN}``.
            Returns None if there are no records in the rolling window.
        """
        cutoff = datetime.now(tz=timezone.utc) - timedelta(
            days=self.rolling_window_days
        )

        window = [
            r for r in self._records
            if datetime.fromisoformat(r["resolved_at"]) >= cutoff
        ]

        if not window:
            log.debug("get_rolling_metrics: no records in the rolling window.")
            return None

        tp = sum(1 for r in window if r["predicted"] == 1 and r["actual"] == 1)
        fp = sum(1 for r in window if r["predicted"] == 1 and r["actual"] == 0)
        tn = sum(1 for r in window if r["predicted"] == 0 and r["actual"] == 0)
        fn = sum(1 for r in window if r["predicted"] == 0 and r["actual"] == 1)

        recall = tp / max(tp + fn, 1)
        fpr    = fp / max(fp + tn, 1)

        metrics = {
            "recall":         round(recall, 5),
            "fpr":            round(fpr, 5),
            "window_records": len(window),
            "window_days":    self.rolling_window_days,
            "TP": tp, "FP": fp, "TN": tn, "FN": fn,
        }

        log.info(
            "Rolling metrics (%d-day window, %d records): "
            "recall=%.4f, FPR=%.4f",
            self.rolling_window_days, len(window), recall, fpr,
        )
        return metrics

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        """Write the full record log to disk."""
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w") as f:
            json.dump(self._records, f, indent=2)

    def _load_existing_log(self) -> None:
        """Load existing records from disk if the log file exists."""
        p = Path(self.log_path)
        if p.exists():
            with open(p) as f:
                self._records = json.load(f)
            log.info(
                "PerformanceTracker: loaded %d existing records from %s.",
                len(self._records), self.log_path,
            )

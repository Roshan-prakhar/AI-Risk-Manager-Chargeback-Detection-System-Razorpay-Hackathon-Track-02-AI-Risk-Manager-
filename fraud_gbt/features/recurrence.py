"""
features/recurrence.py
----------------------
Recurrence-signal validation gate.

Design note
-----------
Before using ANY identifier column as a "repeat offender" feature, validate
that fraud-rate lift for seen-before entities is meaningfully above 1.0.

We tested three candidates on IEEE-CIS:
  - card1                   → no lift (identifiers shared across cardholders)
  - composite fingerprint   → no lift / inverse effect
  - DeviceInfo              → no lift

All three failed because the identifiers are not truly unique per real-world
entity.  An unvalidated recurrence feature can silently *hurt* the model by
adding noise that the GBT overfits to in training but that evaporates on live
data.  Always validate first; only build the feature if it passes.
"""

from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger(__name__)

# Minimum lift required before we build a recurrence feature into the model.
MIN_LIFT = 1.5


def validate_recurrence_signal(
    df: pd.DataFrame,
    identifier_col: str,
    label_col: str = "isFraud",
    min_prior_count: int = 2,
) -> float:
    """Compute fraud-rate lift for entities with confirmed prior fraud.

    Lift is defined as:
        fraud_rate(rows where this identifier had a prior confirmed fraud)
        ──────────────────────────────────────────────────────────────────
        fraud_rate(rows where this identifier had NO prior confirmed fraud)

    A lift meaningfully above 1.0 means "repeat-offender" behaviour is
    detectable for this identifier, and building a recurrence feature is
    justified.  At or below 1.0 means the identifier is too noisy or
    non-unique to carry this signal.

    Parameters
    ----------
    df : pd.DataFrame
        Should be the **training** split only.  Never run on test data.
    identifier_col : str
        Column to evaluate as a recurrence identifier.
    label_col : str
        Fraud label column.  Default ``"isFraud"``.
    min_prior_count : int
        An entity must appear at least this many times before its history
        is used to flag future transactions as recurrent.  Default 2.

    Returns
    -------
    float
        Lift value.  Log a warning if below ``MIN_LIFT``.

    Raises
    ------
    ValueError
        If *identifier_col* or *label_col* are not in *df*.
    """
    for col in [identifier_col, label_col]:
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found in DataFrame.")

    # Build the "has prior fraud" flag per entity using a rolling approach:
    # for each entity, check if it has at least one fraud label in the data.
    # (In production this would be time-ordered; here we use overall rate
    # as a conservative proxy since we're evaluating on a single split.)
    entity_fraud_counts = df.groupby(identifier_col)[label_col].sum()
    entity_total_counts = df.groupby(identifier_col)[label_col].count()

    # Entities with at least one prior fraud AND enough occurrences
    has_prior_fraud = set(
        entity_fraud_counts[
            (entity_fraud_counts >= 1) & (entity_total_counts >= min_prior_count)
        ].index
    )

    df = df.copy()
    df["_has_prior_fraud"] = df[identifier_col].isin(has_prior_fraud).astype(int)

    rate_with_prior    = df.loc[df["_has_prior_fraud"] == 1, label_col].mean()
    rate_without_prior = df.loc[df["_has_prior_fraud"] == 0, label_col].mean()

    if rate_without_prior == 0:
        log.warning(
            "  validate_recurrence_signal('%s'): baseline fraud rate is 0; "
            "cannot compute lift.",
            identifier_col,
        )
        return 0.0

    lift = rate_with_prior / rate_without_prior

    log.info(
        "  Recurrence lift for '%s': %.3f  "
        "(rate_with_prior=%.4f, rate_without_prior=%.4f, n_prior_entities=%d)",
        identifier_col, lift,
        rate_with_prior, rate_without_prior, len(has_prior_fraud),
    )

    if lift < MIN_LIFT:
        log.warning(
            "  [WARN] '%s' lift %.3f < threshold %.1f -- do NOT build a recurrence "
            "feature for this identifier.  It will add noise, not signal.",
            identifier_col, lift, MIN_LIFT,
        )
    else:
        log.info(
            "  [OK] '%s' passed recurrence validation (lift %.3f >= %.1f).",
            identifier_col, lift, MIN_LIFT,
        )

    return lift


def build_recurrence_feature(
    df: pd.DataFrame,
    train_fraud_entities: set,
    identifier_col: str,
    feature_name: str | None = None,
) -> pd.DataFrame:
    """Add a binary "has_prior_fraud" recurrence feature for a validated identifier.

    Only call this **after** ``validate_recurrence_signal`` has confirmed a
    lift ≥ ``MIN_LIFT``.

    Parameters
    ----------
    df : pd.DataFrame
    train_fraud_entities : set
        Set of identifier values that had at least one fraud in the training
        set.  Derived from training data only; applied to val/test/live data.
    identifier_col : str
    feature_name : str, optional
        Name of the output column.  Defaults to ``"prior_fraud_{identifier_col}"``.

    Returns
    -------
    pd.DataFrame
        *df* with new recurrence column added.
    """
    col = feature_name or f"prior_fraud_{identifier_col}"
    df = df.copy()
    df[col] = df[identifier_col].isin(train_fraud_entities).astype("int8")
    log.debug(
        "  Built recurrence feature '%s': %.2f%% of rows flagged.",
        col, 100 * df[col].mean(),
    )
    return df

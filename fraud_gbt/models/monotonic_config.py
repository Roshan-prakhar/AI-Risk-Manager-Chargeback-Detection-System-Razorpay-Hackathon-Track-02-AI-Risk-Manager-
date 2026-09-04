"""
models/monotonic_config.py
--------------------------
Per-feature monotonic constraint directions for LightGBM.

+1  : risk can only increase as this feature increases
-1  : risk can only decrease as this feature increases
 0  : unconstrained

Design rationale
----------------
Monotonic constraints serve two purposes simultaneously:
  1. Regularisation — they prevent the model from learning spurious reversals
     that don't reflect domain logic (e.g. "extremely large amount deviation
     suddenly looks safe").
  2. Explainability / defensibility — each constrained feature can be described
     to a judge or auditor in a single sentence: "our model guarantees that risk
     never decreases as this transaction looks more anomalous."

Only constrain features with a *clear, unambiguous* monotonic business argument.
Forcing constraints on ambiguous features (most V/C/D columns) degrades accuracy
without adding real defensibility.  Don't over-apply this.
"""

from __future__ import annotations

# Feature name → constraint direction
MONOTONIC_CONSTRAINTS: dict[str, int] = {
    # Transactional deviation
    "amt_zscore":          +1,   # more deviation from card baseline → never lower risk
    # Behavioural novelty / rarity
    "card1_freq_in_train": -1,   # more transaction history on this card → never higher risk
    "is_rare_card":        +1,   # card seen rarely in training → never lower risk
    # Missingness signals
    "dist1_missing":       +1,   # absent distance data → never lower risk
    "P_emaildomain_missing": +1, # absent payer email domain → never lower risk
    "addr1_missing":       +1,   # absent billing address → never lower risk
    "dist2_missing":       +1,   # absent dist2 → never lower risk
}


def get_constraint_vector(feature_cols: list[str]) -> list[int]:
    """Return an ordered constraint list aligned to *feature_cols*.

    Parameters
    ----------
    feature_cols : list[str]
        The exact ordered list of feature column names used to build the
        LightGBM dataset.  Order must match the columns in X_train / X_val.

    Returns
    -------
    list[int]
        Same length as *feature_cols*.  Each element is +1, -1, or 0.
        Pass directly to LightGBM's ``monotone_constraints`` parameter.

    Example
    -------
    >>> cols = ["amt_zscore", "V1", "card1_freq_in_train"]
    >>> get_constraint_vector(cols)
    [1, 0, -1]
    """
    if not feature_cols:
        raise ValueError("feature_cols must be a non-empty list.")
    return [MONOTONIC_CONSTRAINTS.get(col, 0) for col in feature_cols]

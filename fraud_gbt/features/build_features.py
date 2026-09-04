"""
features/build_features.py
--------------------------
Three-category feature engineering: transactional, behavioral, temporal/missingness.

Published fraud-detection research on large e-commerce datasets consistently shows
that spanning all three categories drives performance over raw transaction fields
alone.  The IEEE-CIS C/D columns already cover much of this natively, which is
why they dominate gain rankings; our engineered features complement the gaps.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Rarity cutoff: cards seen fewer than this many times in training are flagged
RARITY_CUTOFF = 5


# ---------------------------------------------------------------------------
# Transactional: amount deviation
# ---------------------------------------------------------------------------

def compute_card_stats(train_df: pd.DataFrame,
                       card_col: str = "card1",
                       amt_col: str = "TransactionAmt") -> pd.DataFrame:
    """Compute per-card mean and std from the *training* set only.

    Call this once on ``train_df`` and persist the result; apply to val/test
    via ``add_amount_deviation`` with the precomputed stats.

    Parameters
    ----------
    train_df : pd.DataFrame
    card_col : str
        Card identifier column.
    amt_col : str
        Transaction amount column.

    Returns
    -------
    pd.DataFrame
        Indexed by *card_col* with columns ``["amt_mean", "amt_std"]``.
    """
    stats = (
        train_df.groupby(card_col)[amt_col]
        .agg(amt_mean="mean", amt_std="std")
        .reset_index()
        .set_index(card_col)
    )
    # Cards with a single transaction have NaN std; replace with 0 so the
    # global fallback triggers cleanly in add_amount_deviation.
    stats["amt_std"] = stats["amt_std"].fillna(0.0)
    log.info("Computed card stats for %d unique cards.", len(stats))
    return stats


def add_amount_deviation(
    df: pd.DataFrame,
    card_stats: pd.DataFrame,
    global_mean: float,
    global_std: float,
    card_col: str = "card1",
    amt_col: str = "TransactionAmt",
) -> pd.DataFrame:
    """Add ``amt_zscore``: z-score of TransactionAmt vs this card's history.

    Unseen cards (not in *card_stats*) are filled with the global baseline,
    never with 0 or NaN silently.  A card appearing for the first time is a
    real signal; the global mean is the least-surprising prior, not an
    absence of information.

    Parameters
    ----------
    df : pd.DataFrame
    card_stats : pd.DataFrame
        Output of ``compute_card_stats`` (indexed by *card_col*).
    global_mean : float
        Global mean of TransactionAmt from training set.
    global_std : float
        Global std of TransactionAmt from training set.  Must be > 0.
    card_col : str
    amt_col : str

    Returns
    -------
    pd.DataFrame
        *df* with ``amt_zscore`` column added (in-place copy).
    """
    if global_std <= 0:
        raise ValueError(f"global_std must be > 0; got {global_std}.")

    df = df.copy()
    merged = df[[card_col, amt_col]].join(card_stats, on=card_col, how="left")

    # Fill unseen cards with global statistics
    card_mean = merged["amt_mean"].fillna(global_mean)
    card_std  = merged["amt_std"].fillna(global_std)
    card_std  = card_std.replace(0.0, global_std)      # single-transaction cards

    df["amt_zscore"] = ((df[amt_col] - card_mean) / card_std).astype("float32")

    n_unseen = merged["amt_mean"].isna().sum()
    if n_unseen:
        log.debug(
            "  %d transactions used global fallback for amt_zscore (unseen card).",
            n_unseen,
        )
    return df


# ---------------------------------------------------------------------------
# Behavioral: novelty / rarity flags
# ---------------------------------------------------------------------------

def compute_train_frequencies(
    train_df: pd.DataFrame,
    identifier_col: str,
) -> pd.Series:
    """Count how many times each identifier value appears in training.

    Parameters
    ----------
    train_df : pd.DataFrame
    identifier_col : str
        E.g. ``"card1"``, ``"DeviceInfo"``.

    Returns
    -------
    pd.Series
        Index = identifier value, values = integer counts.
    """
    return train_df[identifier_col].value_counts()


def add_novelty_flags(
    df: pd.DataFrame,
    train_freq_lookup: pd.Series,
    identifier_col: str = "card1",
    rarity_cutoff: int = RARITY_CUTOFF,
) -> pd.DataFrame:
    """Add ``{identifier_col}_freq_in_train`` and ``is_rare_{identifier_col}`` columns.

    Identifiers below *rarity_cutoff* occurrences in training, or absent from
    training entirely, receive ``is_rare_* = 1``.

    **Validate this correlates with fraud before trusting it** (see
    ``recurrence.validate_recurrence_signal``).  On IEEE-CIS, card1-level
    recurrence showed no lift or an inverse effect, because the identifiers
    aren't truly unique per real-world entity.

    Parameters
    ----------
    df : pd.DataFrame
    train_freq_lookup : pd.Series
        Output of ``compute_train_frequencies``.
    identifier_col : str
    rarity_cutoff : int

    Returns
    -------
    pd.DataFrame
        *df* with two new columns added.
    """
    df = df.copy()
    freq_col = f"{identifier_col}_freq_in_train"
    rare_col = f"is_rare_{identifier_col}"

    df[freq_col] = (
        df[identifier_col]
        .map(train_freq_lookup)
        .fillna(0)
        .astype("int32")
    )
    df[rare_col] = (df[freq_col] < rarity_cutoff).astype("int8")

    rare_rate = df[rare_col].mean()
    log.info(
        "  Novelty flag '%s': %.1f%% of rows are rare (cutoff=%d).",
        identifier_col, 100 * rare_rate, rarity_cutoff,
    )
    return df


# ---------------------------------------------------------------------------
# Temporal / missingness flags
# ---------------------------------------------------------------------------

def add_missingness_flags(
    df: pd.DataFrame,
    cols: list[str],
) -> pd.DataFrame:
    """Add explicit ``{col}_missing`` binary flags where nulls are informative.

    On IEEE-CIS, ``dist1``, ``P_emaildomain``, ``addr1``, and ``dist2`` have
    informative missingness — their absence is correlated with fraud patterns,
    not random data collection failure.

    Parameters
    ----------
    df : pd.DataFrame
    cols : list[str]
        Columns for which to create missingness indicators.

    Returns
    -------
    pd.DataFrame
        *df* with one ``{col}_missing`` column added per entry in *cols*.
    """
    df = df.copy()
    for col in cols:
        if col not in df.columns:
            log.warning("  Missingness flag: column '%s' not found; skipping.", col)
            continue
        flag_col = f"{col}_missing"
        df[flag_col] = df[col].isna().astype("int8")
        log.debug(
            "  %s: %.1f%% missing.",
            col, 100 * df[flag_col].mean(),
        )
    return df


# ---------------------------------------------------------------------------
# Convenience: run all engineered features in one call
# ---------------------------------------------------------------------------

def build_all_features(
    df: pd.DataFrame,
    card_stats: pd.DataFrame,
    global_mean: float,
    global_std: float,
    card_freq: pd.Series,
    missingness_cols: list[str],
    card_col: str = "card1",
) -> pd.DataFrame:
    """Apply all three feature categories in sequence.

    Parameters
    ----------
    df : pd.DataFrame
    card_stats : pd.DataFrame
        From ``compute_card_stats`` (fit on train).
    global_mean, global_std : float
        Global TransactionAmt statistics from training set.
    card_freq : pd.Series
        From ``compute_train_frequencies`` (fit on train).
    missingness_cols : list[str]
        Columns for which to create missingness flags.
    card_col : str

    Returns
    -------
    pd.DataFrame
        *df* with all engineered features added.
    """
    df = add_amount_deviation(df, card_stats, global_mean, global_std, card_col)
    df = add_novelty_flags(df, card_freq, card_col)
    df = add_missingness_flags(df, missingness_cols)
    return df

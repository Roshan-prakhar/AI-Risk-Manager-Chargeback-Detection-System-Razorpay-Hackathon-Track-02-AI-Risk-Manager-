"""
features/encoders.py
--------------------
Train-only categorical encoding with safe handling of unseen categories.

Design notes
------------
* Fit on TRAIN ONLY.  Fitting on the full dataset leaks future category
  distributions into the encoder, giving the model implicit access to
  validation/test frequencies during training.

* Store the string→code mapping dict, not just the integer codes, so
  val/test/production can apply the *exact same* mapping.

* Unseen categories (at val/test/serving time) map to a reserved
  '__unknown__' code.  They must never silently become NaN or crash.
"""

from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger(__name__)

UNKNOWN_TOKEN = "__unknown__"
UNKNOWN_CODE  = -1    # integer code assigned to unseen categories


def fit_categorical_encoder(
    train_df: pd.DataFrame,
    cat_cols: list[str],
) -> dict[str, dict]:
    """Fit a category→integer code mapping on training data only.

    Parameters
    ----------
    train_df : pd.DataFrame
        Training split.  Only the distinct values seen here will be assigned
        codes; anything else is mapped to UNKNOWN_CODE at apply time.
    cat_cols : list[str]
        Categorical columns to encode.

    Returns
    -------
    dict[str, dict]
        Mapping of the form:
        ``{ column_name: { category_value: integer_code, ... } }``
        The UNKNOWN_TOKEN key is pre-populated in each sub-dict.

    Example
    -------
    >>> enc = fit_categorical_encoder(train_df, ["ProductCD", "card4"])
    >>> enc["ProductCD"]
    {'W': 0, 'H': 1, 'C': 2, 'S': 3, 'R': 4, '__unknown__': -1}
    """
    encoder: dict[str, dict] = {}
    for col in cat_cols:
        if col not in train_df.columns:
            log.warning("  Encoder: column '%s' not found in train; skipping.", col)
            continue

        # Get unique non-null values and assign sequential codes starting at 0
        unique_vals = sorted(
            v for v in train_df[col].dropna().unique() if v != UNKNOWN_TOKEN
        )
        code_map: dict = {str(v): i for i, v in enumerate(unique_vals)}
        code_map[UNKNOWN_TOKEN] = UNKNOWN_CODE
        encoder[col] = code_map
        log.debug(
            "  Encoder fitted for '%s': %d categories + unknown.",
            col, len(unique_vals),
        )

    log.info("Fitted encoder for %d categorical columns.", len(encoder))
    return encoder


def apply_categorical_encoder(
    df: pd.DataFrame,
    encoder_map: dict[str, dict],
) -> pd.DataFrame:
    """Apply a previously-fit encoder to any DataFrame split.

    This function is designed to be usable standalone at serving time, not
    just inside the training script.  It does not require the training
    DataFrame to be in scope.

    Parameters
    ----------
    df : pd.DataFrame
    encoder_map : dict[str, dict]
        Output of ``fit_categorical_encoder``.

    Returns
    -------
    pd.DataFrame
        *df* copy with each encoded column replaced by its integer code.
        Unseen values and NaN become ``UNKNOWN_CODE`` (-1).
        Original object/category columns are replaced; column names are kept.
    """
    df = df.copy()
    for col, code_map in encoder_map.items():
        if col not in df.columns:
            log.warning("  Encoder apply: column '%s' not in DataFrame; skipping.", col)
            continue

        # Convert to string first so NaN → "nan", then map; nan → UNKNOWN_CODE
        mapped = (
            df[col]
            .astype(str)
            .str.strip()
            .map(code_map)
        )
        # Anything that didn't match (NaN from .map) → UNKNOWN_CODE
        n_unknown = mapped.isna().sum()
        mapped = mapped.fillna(UNKNOWN_CODE).astype("int16")

        if n_unknown:
            log.debug(
                "  Encoder '%s': %d unseen/null values → UNKNOWN_CODE (%d).",
                col, n_unknown, UNKNOWN_CODE,
            )

        df[col] = mapped

    return df


def get_encoder_feature_cols(
    all_cols: list[str],
    encoder_map: dict[str, dict],
) -> list[str]:
    """Return the subset of *all_cols* that the encoder actually covers.

    Convenience helper for bookkeeping when constructing X matrices.

    Parameters
    ----------
    all_cols : list[str]
    encoder_map : dict[str, dict]

    Returns
    -------
    list[str]
    """
    return [c for c in all_cols if c in encoder_map]

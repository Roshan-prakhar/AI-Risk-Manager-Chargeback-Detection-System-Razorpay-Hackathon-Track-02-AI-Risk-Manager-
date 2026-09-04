# Chargeback Fraud Model — Baseline

## Files
- `chargeback_fraud_model.txt` — trained LightGBM model (native format, load with `lightgbm.Booster(model_file=...)`)
- `model_feature_list.txt` — exact feature column order the model expects, in order

## Key numbers (held-out test set, never used in training or threshold selection)
- AUC: 0.84
- Chosen threshold: 0.07 (minimum-cost threshold on validation set, see cost matrix below)
- At this threshold: recall 69.3%, precision 13.0%
- Test set fraud rate: 3.48%

## Cost matrix used for threshold selection (stated assumptions, not real Razorpay figures)
- False negative (missed fraud): ~$145.64, the average fraud transaction amount in training data
- False positive (legit transaction flagged): $5.00 flat review/friction cost

## How to load and score a new transaction
```python
import lightgbm as lgb
import pandas as pd

model = lgb.Booster(model_file='chargeback_fraud_model.txt')

with open('model_feature_list.txt') as f:
    feature_cols = f.read().splitlines()

# new_transaction_df must have all columns in feature_cols, engineered the same way
# as in step2_features.py (amt_zscore, is_rare_card, categorical codes, etc.)
probs = model.predict(new_transaction_df[feature_cols])
is_flagged = probs >= 0.07
```

## What this model does NOT yet include
- Tier routing (Trivial/Moderate/High bands) — only a single binary threshold exists right now
- Value-threshold lane logic — the "route high-value transactions to heavier scrutiny" rule
- Persistent account-level risk memory across transactions over time
- Delivery confirmation signal — not present in the IEEE-CIS dataset, needs to be simulated or
  sourced separately for the full chargeback pipeline
- The LLM verifier / dispute-time reasoning layer

This is the Stage 1 baseline risk scorer only. See the architecture PDF for how it fits into
the full 5-stage pipeline.

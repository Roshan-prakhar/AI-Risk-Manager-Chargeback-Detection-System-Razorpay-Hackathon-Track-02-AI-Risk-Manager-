import pandas as pd
from fraud_gbt import config as cfg
from fraud_gbt.serving.score import load_scorer

def main():
    print("Loading test data...")
    # Read a few rows from the test transaction data
    df = pd.read_csv(cfg.TEST_TRANSACTION_CSV, nrows=10)
    
    # Initialize the scorer
    print("Initializing FraudScorer...")
    scorer = load_scorer(
        model_path=str(cfg.MODEL_PATH),
        calibrator_path=str(cfg.CALIBRATOR_PATH),
        encoder_path=str(cfg.ENCODER_PATH),
        train_stats_path=str(cfg.TRAIN_STATS_PATH),
        threshold=0.11  # optimal threshold from our metrics report
    )
    
    print("\nScoring first transaction:")
    tx_dict = df.iloc[0].to_dict()
    # TransactionID is typically excluded from scoring but is fine in the dict
    print(f"Transaction ID: {tx_dict['TransactionID']} | Amount: ${tx_dict['TransactionAmt']}")
    
    result = scorer.score_transaction(tx_dict)
    
    print("\nResult:")
    for k, v in result.items():
        print(f"  {k}: {v}")
        
    print("\nScoring a batch of 5 transactions:")
    batch_df = df.head(5)
    batch_result = scorer.score_batch(batch_df)
    
    print(batch_result[["TransactionID", "TransactionAmt", "raw_prob", "calibrated_prob", "decision"]])

if __name__ == "__main__":
    main()

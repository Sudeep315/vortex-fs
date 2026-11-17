"""
Example 3: Point-in-Time Correct (ASOF) Training Dataset Generation
Demonstrates how VortexFS eliminates Training-Serving Skew and Target Data Leakage.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone, timedelta
import pandas as pd
from vortex.serving.client import FeatureStoreClient
from vortex.core.event import Event


def main():
    print("=== VortexFS: Point-in-Time Correctness & Zero Leakage Demo ===")
    client = FeatureStoreClient()

    user_id = "test_user_pit"
    t_obs = datetime(2026, 7, 10, 14, 0, 0, tzinfo=timezone.utc)

    print(f"\nTarget Observation Timestamp (T_obs): {t_obs.isoformat()}")

    # 1. Simulate historical event 3 hours BEFORE observation point
    event_past = Event(
        event="payment_executed",
        distinct_id=user_id,
        timestamp=t_obs - timedelta(hours=3),
        properties={"amount": 80.0}
    )

    # 2. Simulate future event 30 minutes AFTER observation point
    event_future = Event(
        event="payment_executed",
        distinct_id=user_id,
        timestamp=t_obs + timedelta(minutes=30),
        properties={"amount": 950.0}
    )

    # Ingest and flush into offline store
    client.ingest_batch([event_past, event_future])
    client.flush()
    print("✓ Ingested 1 past event ($80.00) and 1 future event ($950.00) relative to T_obs.")

    # 3. Define historical observation point (e.g. historical loan/credit request or transaction)
    observation_df = pd.DataFrame([{
        "user_id": user_id,
        "timestamp": t_obs,
        "is_fraud": 0,
    }])

    # 4. Execute Point-in-Time Historical Join
    print("\nExecuting Vectorized ASOF Join against DuckDB columnar store...")
    feature_refs = [
        "user_fraud_features:transaction_count_24h",
        "user_fraud_features:total_spend_24h",
    ]

    training_df = client.get_historical_features(
        observation_df=observation_df,
        entity_key="user_id",
        feature_refs=feature_refs,
    )

    print("\nResulting Point-in-Time Correct Training Row:")
    print(training_df.to_string(index=False))

    # Assertions
    val_spend = training_df.iloc[0]["total_spend_24h"]
    val_tx = training_df.iloc[0]["transaction_count_24h"]

    print(f"\nVerification:")
    print(f"  Total Spend Joined: ${val_spend:.2f} (Expected: $80.00)")
    print(f"  Transaction Count Joined: {val_tx} (Expected: 1)")

    if val_spend == 80.0 and val_tx == 1:
        print("\n>>> ZERO TARGET DATA LEAKAGE CONFIRMED! Future $950 event was successfully ignored.")
    else:
        print("\n>>> DATA LEAKAGE DETECTED! Future event leaked into historical features.")


if __name__ == "__main__":
    main()

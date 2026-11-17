"""
Example 2: Real-Time Stream Ingestion & Sliding Window Aggregation
Demonstrates how incoming events trigger real-time feature calculations and sync to Online Storage.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone, timedelta
from vortex.serving.client import FeatureStoreClient
from vortex.core.event import Event


def main():
    print("=== VortexFS: Real-Time Stream Ingestion Demo ===")
    client = FeatureStoreClient()

    user_id = "user_driver_88"
    now = datetime.now(timezone.utc)

    print(f"\n1. Ingesting stream events for {user_id}...")

    # Event 1: Failed login attempt 20 mins ago
    client.ingest(Event(
        event="login_failed",
        distinct_id=user_id,
        timestamp=now - timedelta(minutes=20),
        properties={"reason": "bad_password"}
    ))

    # Event 2: Another failed login attempt 5 mins ago
    client.ingest(Event(
        event="login_failed",
        distinct_id=user_id,
        timestamp=now - timedelta(minutes=5),
        properties={"reason": "mfa_timeout"}
    ))

    # Event 3: Payment of $240 executed 2 mins ago
    client.ingest(Event(
        event="payment_executed",
        distinct_id=user_id,
        timestamp=now - timedelta(minutes=2),
        properties={"amount": 240.0, "currency": "USD"}
    ))

    # Event 4: Payment of $110 executed now
    client.ingest(Event(
        event="payment_executed",
        distinct_id=user_id,
        timestamp=now,
        properties={"amount": 110.0, "currency": "USD"}
    ))

    print("✓ Events processed through sliding windows.")

    # 2. Query Online Store (< 5ms point lookup)
    print("\n2. Fetching real-time features from Online Store...")
    features_to_fetch = [
        "user_fraud_features:failed_logins_1h",
        "user_fraud_features:transaction_count_10m",
        "user_fraud_features:total_spend_24h",
        "user_fraud_features:avg_spend_7d",
    ]

    records = client.get_online_features(
        entity_name="user",
        entity_ids=[user_id],
        feature_refs=features_to_fetch,
    )

    print(f"\nRetrieved Online Feature Record for {user_id}:")
    for key, val in records[0].items():
        print(f"  • {key}: {val}")

    # Flush buffer to offline store
    flushed = client.flush()
    print(f"\n✓ Micro-batch buffer flushed {flushed} events to DuckDB columnar store.")


if __name__ == "__main__":
    main()

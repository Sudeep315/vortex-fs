import pytest
import pandas as pd
from datetime import datetime, timezone, timedelta
from vortex.core.event import Event
from vortex.core.registry import FeatureRegistry
from vortex.storage.offline.duckdb_store import DuckDBOfflineStore
from vortex.engine.asof_join import PointInTimeJoinEngine


def test_asof_join_prevents_future_data_leakage(tmp_path):
    """
    CRITICAL DATA ENGINEERING TEST:
    Verifies that events occurring AFTER an observation timestamp are strictly omitted
    from historical feature joins (Zero Target Leakage).
    """
    reg = FeatureRegistry.load_default_demo_registry()
    db_path = tmp_path / "asof_test.duckdb"
    offline_store = DuckDBOfflineStore(db_path=db_path)
    join_engine = PointInTimeJoinEngine(reg, offline_store)

    t_obs = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Event 1: PAST event (1 hour before observation) -> SHOULD BE INCLUDED
    past_event = Event(
        event="payment_executed",
        distinct_id="user_target",
        timestamp=t_obs - timedelta(hours=1),
        properties={"amount": 150.0},
    )

    # Event 2: FUTURE event (15 minutes after observation) -> MUST BE EXCLUDED!
    future_event = Event(
        event="payment_executed",
        distinct_id="user_target",
        timestamp=t_obs + timedelta(minutes=15),
        properties={"amount": 900.0},
    )

    offline_store.write_events([past_event, future_event])

    # Observation at t_obs
    observations = pd.DataFrame([{
        "user_id": "user_target",
        "timestamp": t_obs,
        "is_fraud": 0,
    }])

    features = [
        "user_fraud_features:transaction_count_24h",
        "user_fraud_features:total_spend_24h",
    ]

    joined_df = join_engine.get_historical_features(
        observation_df=observations,
        entity_key="user_id",
        feature_refs=features,
    )

    row = joined_df.iloc[0]

    # Verify that ONLY the past event ($150) is included, and the future $900 event was filtered out!
    assert row["transaction_count_24h"] == 1, f"Expected 1 tx, got {row['transaction_count_24h']}"
    assert row["total_spend_24h"] == 150.0, f"Expected $150.0, got ${row['total_spend_24h']} (Data Leakage Detected if $1050 or $900!)"

    offline_store.close()

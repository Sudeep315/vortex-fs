import pytest
from datetime import datetime, timezone, timedelta
from vortex.core.event import Event
from vortex.core.registry import FeatureRegistry
from vortex.storage.online.memory_store import MemoryOnlineStore
from vortex.storage.offline.duckdb_store import DuckDBOfflineStore
from vortex.engine.stream_processor import StreamProcessor


def test_sliding_window_aggregations(tmp_path):
    reg = FeatureRegistry.load_default_demo_registry()
    online_store = MemoryOnlineStore()
    duckdb_path = tmp_path / "test_offline.duckdb"
    offline_store = DuckDBOfflineStore(db_path=duckdb_path)

    processor = StreamProcessor(reg, online_store, offline_store)

    now = datetime.now(timezone.utc)

    # Ingest 3 payment events for user_alpha
    e1 = Event(event="payment_executed", distinct_id="user_alpha", timestamp=now - timedelta(minutes=5), properties={"amount": 100.0})
    e2 = Event(event="payment_executed", distinct_id="user_alpha", timestamp=now - timedelta(minutes=2), properties={"amount": 50.0})
    e3 = Event(event="payment_executed", distinct_id="user_alpha", timestamp=now, properties={"amount": 75.0})

    processor.ingest_event(e1)
    processor.ingest_event(e2)
    processor.ingest_event(e3)

    # Check online store directly
    features = online_store.read_features(
        entity_name="user",
        entity_ids=["user_alpha"],
        feature_view_name="user_fraud_features",
        feature_names=["transaction_count_10m", "total_spend_24h", "avg_spend_7d"]
    )

    alpha_feats = features["user_alpha"]
    assert alpha_feats["transaction_count_10m"] == 3
    assert alpha_feats["total_spend_24h"] == 225.0
    assert round(alpha_feats["avg_spend_7d"], 2) == 75.0

    offline_store.close()

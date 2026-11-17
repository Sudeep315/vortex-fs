import json
from typing import Any, Dict, List, Optional
import pandas as pd
from datetime import datetime, timezone
from vortex.core.event import Event
from vortex.storage.base import BaseOfflineStore


class ClickHouseOfflineStore(BaseOfflineStore):
    """
    Production scale-out ClickHouse offline store, mirroring PostHog's
    proven high-throughput columnar event ingestion and partitioning model.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9000,
        user: str = "default",
        password: str = "",
        database: str = "vortex",
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self._client = None
        self._init_client()

    def _init_client(self):
        try:
            # We attempt importing clickhouse_connect if installed
            import clickhouse_connect
            self._client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
            )
            self._client.command(f"CREATE DATABASE IF NOT EXISTS {self.database}")
            self._client.database = self.database
            self._create_tables()
        except Exception:
            # ClickHouse not accessible directly in local environment without Docker running
            self._client = None

    def _create_tables(self):
        if not self._client:
            return
        self._client.command("""
            CREATE TABLE IF NOT EXISTS events (
                id String,
                event LowCardinality(String),
                distinct_id String,
                timestamp DateTime64(6, 'UTC'),
                properties String,
                ingested_at DateTime64(6, 'UTC')
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (event, distinct_id, timestamp);
        """)

        self._client.command("""
            CREATE TABLE IF NOT EXISTS feature_snapshots (
                feature_view LowCardinality(String),
                entity_id String,
                timestamp DateTime64(6, 'UTC'),
                feature_values String
            ) ENGINE = ReplacingMergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (feature_view, entity_id, timestamp);
        """)

    def write_events(self, events: List[Event]) -> int:
        if not self._client:
            raise RuntimeError(f"ClickHouse offline store not connected to {self.host}:{self.port}")
        if not events:
            return 0

        rows = []
        now_utc = datetime.now(timezone.utc)
        for ev in events:
            rows.append([
                ev.id,
                ev.event,
                ev.distinct_id,
                ev.timestamp,
                json.dumps(ev.properties),
                now_utc,
            ])

        self._client.insert("events", rows, column_names=["id", "event", "distinct_id", "timestamp", "properties", "ingested_at"])
        return len(events)

    def write_feature_records(self, records_df: pd.DataFrame, feature_view_name: str) -> int:
        if not self._client:
            raise RuntimeError(f"ClickHouse offline store not connected to {self.host}:{self.port}")
        if records_df.empty:
            return 0

        df = records_df.copy()
        df["feature_view"] = feature_view_name
        self._client.insert_df("feature_snapshots", df)
        return len(df)

    def query(self, sql: str) -> pd.DataFrame:
        if not self._client:
            raise RuntimeError(f"ClickHouse offline store not connected to {self.host}:{self.port}")
        return self._client.query_df(sql)

    def get_stats(self) -> Dict[str, Any]:
        if not self._client:
            return {
                "type": "clickhouse",
                "connected": False,
                "host": self.host,
                "port": self.port,
                "database": self.database,
            }
        try:
            event_count = self._client.command("SELECT count() FROM events")
            snapshot_count = self._client.command("SELECT count() FROM feature_snapshots")
            return {
                "type": "clickhouse",
                "connected": True,
                "host": self.host,
                "port": self.port,
                "database": self.database,
                "total_events": event_count,
                "total_feature_snapshots": snapshot_count,
            }
        except Exception as e:
            return {
                "type": "clickhouse",
                "connected": False,
                "error": str(e),
            }

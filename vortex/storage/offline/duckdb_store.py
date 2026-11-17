import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
import duckdb
import pandas as pd
from datetime import datetime, timezone
from vortex.core.event import Event
from vortex.storage.base import BaseOfflineStore


class DuckDBOfflineStore(BaseOfflineStore):
    """
    Embedded high-performance columnar offline store utilizing DuckDB.
    Supports high-speed event batch appends, vectorized analytical queries,
    and ASOF point-in-time joins with zero data leakage.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._con = duckdb.connect(str(self.db_path))
        self._init_db()

    def get_connection(self):
        """Returns the shared thread-safe DuckDB connection."""
        return self._con

    def _init_db(self):
        with self._lock:
            # 1. Raw event log table (PostHog-style immutable append-only event stream)
            self._con.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id VARCHAR PRIMARY KEY,
                    event VARCHAR NOT NULL,
                    distinct_id VARCHAR NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,
                    properties JSON,
                    ingested_at TIMESTAMPTZ NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_lookup 
                ON events (distinct_id, timestamp);
            """)

            # 2. Materialized feature table registry
            self._con.execute("""
                CREATE TABLE IF NOT EXISTS feature_snapshots (
                    feature_view VARCHAR NOT NULL,
                    entity_id VARCHAR NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,
                    feature_values JSON NOT NULL,
                    PRIMARY KEY (feature_view, entity_id, timestamp)
                );
                CREATE INDEX IF NOT EXISTS idx_snapshots_lookup 
                ON feature_snapshots (feature_view, entity_id, timestamp);
            """)

    def write_events(self, events: List[Event]) -> int:
        if not events:
            return 0

        rows = []
        now_utc = datetime.now(timezone.utc)
        for ev in events:
            rows.append((
                ev.id,
                ev.event,
                ev.distinct_id,
                ev.timestamp,
                json.dumps(ev.properties),
                now_utc,
            ))

        df = pd.DataFrame(
            rows,
            columns=["id", "event", "distinct_id", "timestamp", "properties", "ingested_at"]
        )

        with self._lock:
            self._con.register("incoming_events_df", df)
            self._con.execute("""
                INSERT OR IGNORE INTO events 
                SELECT id, event, distinct_id, timestamp, properties, ingested_at 
                FROM incoming_events_df;
            """)
            self._con.unregister("incoming_events_df")

        return len(events)

    def write_feature_records(
        self,
        records_df: pd.DataFrame,
        feature_view_name: str,
    ) -> int:
        """
        Inserts snapshot dataframe with columns: [entity_id, timestamp, feature_values]
        """
        if records_df.empty:
            return 0

        df = records_df.copy()
        df["feature_view"] = feature_view_name

        with self._lock:
            self._con.register("incoming_snapshots_df", df)
            self._con.execute("""
                INSERT OR REPLACE INTO feature_snapshots 
                SELECT feature_view, entity_id, timestamp, feature_values 
                FROM incoming_snapshots_df;
            """)
            self._con.unregister("incoming_snapshots_df")

        return len(df)

    def query(self, sql: str) -> pd.DataFrame:
        with self._lock:
            return self._con.execute(sql).df()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            event_count = self._con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            snapshot_count = self._con.execute("SELECT COUNT(*) FROM feature_snapshots").fetchone()[0]
            distinct_entities = self._con.execute("SELECT COUNT(DISTINCT distinct_id) FROM events").fetchone()[0]
            distinct_event_names = self._con.execute("SELECT COUNT(DISTINCT event) FROM events").fetchone()[0]

            size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0

            return {
                "type": "duckdb",
                "db_path": str(self.db_path),
                "total_events": event_count,
                "distinct_entities": distinct_entities,
                "distinct_event_types": distinct_event_names,
                "total_feature_snapshots": snapshot_count,
                "file_size_mb": round(size_bytes / (1024 * 1024), 2),
            }

    def close(self):
        with self._lock:
            if self._con:
                self._con.close()

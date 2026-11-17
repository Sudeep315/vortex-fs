import time
import threading
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from vortex.core.event import Event
from vortex.core.feature import FeatureView, FeatureAggregation
from vortex.core.types import AggregationType
from vortex.core.registry import FeatureRegistry
from vortex.storage.base import BaseOnlineStore, BaseOfflineStore


class SlidingWindowEventState:
    """
    Maintains rolling state of recent events for an entity within sliding windows.
    Stores timestamped entries: (timestamp_epoch, property_val)
    """

    def __init__(self):
        # event_name -> list of (timestamp_epoch, property_dict)
        self.history: Dict[str, List[tuple[float, Dict[str, Any]]]] = defaultdict(list)

    def append(self, event_name: str, ts_epoch: float, properties: Dict[str, Any], max_retention_sec: float = 86400 * 30):
        self.history[event_name].append((ts_epoch, properties))
        # Prune older than max retention
        cutoff = ts_epoch - max_retention_sec
        self.history[event_name] = [
            (ts, props) for ts, props in self.history[event_name] if ts >= cutoff
        ]

    def compute_agg(
        self,
        event_name: str,
        target_field: Optional[str],
        agg_func: AggregationType,
        window_seconds: int,
        current_time_epoch: float,
    ) -> Any:
        cutoff = current_time_epoch - window_seconds
        records = [
            props for ts, props in self.history[event_name]
            if cutoff <= ts <= current_time_epoch
        ]

        if agg_func == AggregationType.COUNT:
            return len(records)

        values = []
        for r in records:
            if target_field and target_field in r:
                try:
                    values.append(float(r[target_field]))
                except (ValueError, TypeError):
                    pass

        if not values:
            if agg_func in (AggregationType.SUM, AggregationType.COUNT):
                return 0.0
            return 0.0

        if agg_func == AggregationType.SUM:
            return sum(values)
        elif agg_func == AggregationType.AVG:
            return sum(values) / len(values)
        elif agg_func == AggregationType.MIN:
            return min(values)
        elif agg_func == AggregationType.MAX:
            return max(values)
        elif agg_func == AggregationType.DISTINCT_COUNT:
            raw_vals = [r.get(target_field) for r in records if target_field and target_field in r]
            return len(set(raw_vals))
        elif agg_func == AggregationType.LAST:
            return values[-1] if values else None
        elif agg_func == AggregationType.FIRST:
            return values[0] if values else None

        return 0.0


class StreamProcessor:
    """
    High-throughput stream processing worker. Consumes incoming events,
    computes real-time sliding window feature aggregations, immediately
    syncs to the Online Store for sub-10ms model inference, and buffers
    raw events for micro-batch flushing to the Offline Store.
    """

    def __init__(
        self,
        registry: FeatureRegistry,
        online_store: BaseOnlineStore,
        offline_store: BaseOfflineStore,
        batch_flush_size: int = 200,
        flush_interval_sec: float = 1.0,
    ):
        self.registry = registry
        self.online_store = online_store
        self.offline_store = offline_store
        self.batch_flush_size = batch_flush_size
        self.flush_interval_sec = flush_interval_sec

        self._lock = threading.RLock()
        # entity_name -> entity_id -> SlidingWindowEventState
        self._entity_states: Dict[str, Dict[str, SlidingWindowEventState]] = defaultdict(lambda: defaultdict(SlidingWindowEventState))
        self._offline_buffer: List[Event] = []
        self._last_flush_time = time.time()
        self._total_events_processed = 0
        self._running = False
        self._flush_thread: Optional[threading.Thread] = None

    def start_background_flusher(self):
        """Starts a background daemon thread that periodically flushes offline buffer."""
        if self._running:
            return
        self._running = True
        self._flush_thread = threading.Thread(target=self._flusher_loop, daemon=True)
        self._flush_thread.start()

    def stop_background_flusher(self):
        self._running = False
        self.flush()

    def _flusher_loop(self):
        while self._running:
            time.sleep(self.flush_interval_sec)
            now = time.time()
            if now - self._last_flush_time >= self.flush_interval_sec or len(self._offline_buffer) >= self.batch_flush_size:
                self.flush()

    def ingest_event(self, event: Event) -> Dict[str, Any]:
        """
        Process a single incoming event:
        1. Buffer event for offline store.
        2. Find all matching FeatureViews and update sliding window state.
        3. Write updated features to online store.
        """
        ts_epoch = event.timestamp.timestamp()

        updated_views: Dict[str, Dict[str, Any]] = {}

        with self._lock:
            self._offline_buffer.append(event)
            self._total_events_processed += 1

            # Match against registered FeatureViews
            for fv in self.registry.list_feature_views():
                primary_entity = fv.primary_entity.name
                relevant_aggs = [agg for agg in fv.aggregations if agg.event_name == event.event]

                if not relevant_aggs:
                    continue

                entity_state = self._entity_states[primary_entity][event.distinct_id]
                entity_state.append(event.event, ts_epoch, event.properties)

                # Recompute features for this view
                current_feature_values: Dict[str, Any] = {}
                for agg in fv.aggregations:
                    val = entity_state.compute_agg(
                        event_name=agg.event_name,
                        target_field=agg.target_field,
                        agg_func=agg.agg_func,
                        window_seconds=agg.window.seconds,
                        current_time_epoch=ts_epoch,
                    )
                    current_feature_values[agg.feature_name] = val

                # Online Store Write
                self.online_store.write_features(
                    entity_name=primary_entity,
                    entity_id=event.distinct_id,
                    feature_view_name=fv.name,
                    feature_values=current_feature_values,
                    timestamp=event.timestamp,
                    ttl_seconds=fv.ttl_seconds,
                )
                updated_views[fv.name] = current_feature_values

            # Auto-flush if batch size exceeded
            if len(self._offline_buffer) >= self.batch_flush_size:
                self.flush()

        return updated_views

    def ingest_batch(self, events: List[Event]) -> int:
        for ev in events:
            self.ingest_event(ev)
        return len(events)

    def flush(self) -> int:
        """Flushes buffered events to the offline store."""
        with self._lock:
            if not self._offline_buffer:
                return 0
            batch = self._offline_buffer
            self._offline_buffer = []
            self._last_flush_time = time.time()

        written = self.offline_store.write_events(batch)
        return written

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            tracked_entities_count = sum(len(subdict) for subdict in self._entity_states.values())
            return {
                "total_events_processed": self._total_events_processed,
                "buffered_events_pending_flush": len(self._offline_buffer),
                "tracked_entities_in_memory": tracked_entities_count,
            }

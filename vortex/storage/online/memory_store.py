import time
import threading
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from vortex.storage.base import BaseOnlineStore


class MemoryOnlineStore(BaseOnlineStore):
    """
    High-performance thread-safe in-memory key-value store with TTL support
    and telemetry for local execution, tests, and micro-benchmarks.
    """

    def __init__(self):
        self._lock = threading.RLock()
        # Storage format: { f"{entity_name}:{entity_id}:{feature_view}": {"data": dict, "expires_at": float, "updated_at": str} }
        self._store: Dict[str, Dict[str, Any]] = {}
        self._total_reads = 0
        self._total_writes = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._latencies_ms: List[float] = []

    def _make_key(self, entity_name: str, entity_id: str, feature_view_name: str) -> str:
        return f"{entity_name}:{entity_id}:{feature_view_name}"

    def write_features(
        self,
        entity_name: str,
        entity_id: str,
        feature_view_name: str,
        feature_values: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        start_time = time.perf_counter()
        key = self._make_key(entity_name, entity_id, feature_view_name)
        now_ts = time.time()
        expires_at = (now_ts + ttl_seconds) if ttl_seconds else float("inf")
        ts_str = (timestamp or datetime.now(timezone.utc)).isoformat()

        with self._lock:
            existing = self._store.get(key)
            if existing and existing["expires_at"] > now_ts:
                # Merge existing features with new updates
                merged = existing["data"].copy()
                merged.update(feature_values)
                self._store[key] = {
                    "data": merged,
                    "expires_at": expires_at,
                    "updated_at": ts_str,
                }
            else:
                self._store[key] = {
                    "data": feature_values.copy(),
                    "expires_at": expires_at,
                    "updated_at": ts_str,
                }
            self._total_writes += 1

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._record_latency(elapsed_ms)

    def read_features(
        self,
        entity_name: str,
        entity_ids: List[str],
        feature_view_name: str,
        feature_names: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        start_time = time.perf_counter()
        results: Dict[str, Dict[str, Any]] = {}
        now_ts = time.time()

        with self._lock:
            for eid in entity_ids:
                key = self._make_key(entity_name, eid, feature_view_name)
                entry = self._store.get(key)
                entity_feats: Dict[str, Any] = {}

                if entry and entry["expires_at"] > now_ts:
                    data = entry["data"]
                    for fn in feature_names:
                        if fn in data:
                            entity_feats[fn] = data[fn]
                            self._cache_hits += 1
                        else:
                            entity_feats[fn] = None
                            self._cache_misses += 1
                    entity_feats["__updated_at"] = entry["updated_at"]
                else:
                    for fn in feature_names:
                        entity_feats[fn] = None
                        self._cache_misses += 1
                    entity_feats["__updated_at"] = None

                results[eid] = entity_feats
            self._total_reads += len(entity_ids)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._record_latency(elapsed_ms)
        return results

    def _record_latency(self, ms: float) -> None:
        if len(self._latencies_ms) > 1000:
            self._latencies_ms.pop(0)
        self._latencies_ms.append(ms)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            now_ts = time.time()
            active_keys = sum(1 for v in self._store.values() if v["expires_at"] > now_ts)
            total_requests = self._cache_hits + self._cache_misses
            hit_rate = (self._cache_hits / total_requests * 100.0) if total_requests > 0 else 0.0

            sorted_lat = sorted(self._latencies_ms) if self._latencies_ms else [0.0]
            n = len(sorted_lat)
            p50 = sorted_lat[int(n * 0.50)]
            p95 = sorted_lat[min(int(n * 0.95), n - 1)]
            p99 = sorted_lat[min(int(n * 0.99), n - 1)]

            return {
                "type": "memory",
                "active_keys": active_keys,
                "total_writes": self._total_writes,
                "total_reads": self._total_reads,
                "cache_hit_rate_pct": round(hit_rate, 2),
                "p50_latency_ms": round(p50, 3),
                "p95_latency_ms": round(p95, 3),
                "p99_latency_ms": round(p99, 3),
            }

import time
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from vortex.storage.base import BaseOnlineStore


class RedisOnlineStore(BaseOnlineStore):
    """
    Production-grade Redis Online Store utilizing Redis hashes and pipelines
    for sub-millisecond batch lookups.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._client = None
        self._latencies_ms: List[float] = []
        self._total_reads = 0
        self._total_writes = 0
        self._init_client()

    def _init_client(self):
        try:
            import redis
            self._client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            # Test ping
            self._client.ping()
        except Exception as e:
            # We keep _client initialized, but will raise friendly error if operations fail
            pass

    def _make_key(self, entity_name: str, entity_id: str, feature_view_name: str) -> str:
        return f"vortex:fs:{entity_name}:{entity_id}:{feature_view_name}"

    def write_features(
        self,
        entity_name: str,
        entity_id: str,
        feature_view_name: str,
        feature_values: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        if not self._client:
            raise RuntimeError(f"Redis client not connected to {self.redis_url}")

        start_time = time.perf_counter()
        key = self._make_key(entity_name, entity_id, feature_view_name)
        payload = {k: json.dumps(v) for k, v in feature_values.items()}
        payload["__updated_at"] = (timestamp or datetime.now(timezone.utc)).isoformat()

        pipe = self._client.pipeline()
        pipe.hset(key, mapping=payload)
        if ttl_seconds:
            pipe.expire(key, ttl_seconds)
        pipe.execute()

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
        if not self._client:
            raise RuntimeError(f"Redis client not connected to {self.redis_url}")

        start_time = time.perf_counter()
        pipe = self._client.pipeline()
        keys = [self._make_key(entity_name, eid, feature_view_name) for eid in entity_ids]

        # Pipeline HMGET across all entity keys
        lookup_fields = feature_names + ["__updated_at"]
        for k in keys:
            pipe.hmget(k, lookup_fields)

        batch_results = pipe.execute()
        results: Dict[str, Dict[str, Any]] = {}

        for eid, row in zip(entity_ids, batch_results):
            entity_feats: Dict[str, Any] = {}
            # row has values in same order as lookup_fields
            for idx, fn in enumerate(feature_names):
                val_raw = row[idx]
                if val_raw is not None:
                    try:
                        entity_feats[fn] = json.loads(val_raw)
                    except (json.JSONDecodeError, TypeError):
                        entity_feats[fn] = val_raw
                else:
                    entity_feats[fn] = None

            updated_at_raw = row[-1]
            entity_feats["__updated_at"] = updated_at_raw
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
        info = {}
        is_connected = False
        try:
            if self._client:
                info = self._client.info()
                is_connected = True
        except Exception:
            pass

        sorted_lat = sorted(self._latencies_ms) if self._latencies_ms else [0.0]
        n = len(sorted_lat)
        p50 = sorted_lat[int(n * 0.50)]
        p95 = sorted_lat[min(int(n * 0.95), n - 1)]
        p99 = sorted_lat[min(int(n * 0.99), n - 1)]

        return {
            "type": "redis",
            "connected": is_connected,
            "redis_version": info.get("redis_version", "unknown"),
            "used_memory_human": info.get("used_memory_human", "N/A"),
            "total_writes": self._total_writes,
            "total_reads": self._total_reads,
            "p50_latency_ms": round(p50, 3),
            "p95_latency_ms": round(p95, 3),
            "p99_latency_ms": round(p99, 3),
        }

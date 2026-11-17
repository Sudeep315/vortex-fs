from vortex.config import settings
from vortex.storage.base import BaseOnlineStore, BaseOfflineStore
from vortex.storage.online.memory_store import MemoryOnlineStore
from vortex.storage.online.redis_store import RedisOnlineStore
from vortex.storage.offline.duckdb_store import DuckDBOfflineStore
from vortex.storage.offline.clickhouse_store import ClickHouseOfflineStore


def get_online_store(store_type: str = None) -> BaseOnlineStore:
    target_type = store_type or settings.ONLINE_STORE_TYPE
    if target_type == "redis":
        try:
            store = RedisOnlineStore(redis_url=settings.REDIS_URL)
            # Test connectivity
            store.get_stats()
            return store
        except Exception:
            # Fallback to memory store if Redis is unavailable
            return MemoryOnlineStore()
    return MemoryOnlineStore()


def get_offline_store(store_type: str = None) -> BaseOfflineStore:
    target_type = store_type or settings.OFFLINE_STORE_TYPE
    if target_type == "clickhouse":
        try:
            store = ClickHouseOfflineStore(
                host=settings.CLICKHOUSE_HOST,
                port=settings.CLICKHOUSE_PORT,
                user=settings.CLICKHOUSE_USER,
                password=settings.CLICKHOUSE_PASSWORD,
                database=settings.CLICKHOUSE_DB,
            )
            stats = store.get_stats()
            if stats.get("connected"):
                return store
        except Exception:
            pass
    # Default to robust embedded DuckDB store
    return DuckDBOfflineStore(db_path=settings.DUCKDB_PATH)


__all__ = [
    "BaseOnlineStore",
    "BaseOfflineStore",
    "MemoryOnlineStore",
    "RedisOnlineStore",
    "DuckDBOfflineStore",
    "ClickHouseOfflineStore",
    "get_online_store",
    "get_offline_store",
]

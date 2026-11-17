from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
import pandas as pd
from vortex.core.event import Event


class BaseOnlineStore(ABC):
    """
    Abstract interface for low-latency online feature serving.
    """

    @abstractmethod
    def write_features(
        self,
        entity_name: str,
        entity_id: str,
        feature_view_name: str,
        feature_values: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """Upsert feature values for a specific entity into the online store."""
        pass

    @abstractmethod
    def read_features(
        self,
        entity_name: str,
        entity_ids: List[str],
        feature_view_name: str,
        feature_names: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Retrieve requested features for multiple entity IDs.
        Returns: {entity_id: {feature_name: value}}
        """
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Return operational metrics (key counts, latencies, memory)."""
        pass


class BaseOfflineStore(ABC):
    """
    Abstract interface for high-throughput columnar storage and historical queries.
    """

    @abstractmethod
    def write_events(self, events: List[Event]) -> int:
        """Append raw events to the columnar event log."""
        pass

    @abstractmethod
    def write_feature_records(
        self,
        records_df: pd.DataFrame,
        feature_view_name: str,
    ) -> int:
        """Append materialized historical feature snapshots."""
        pass

    @abstractmethod
    def query(self, sql: str) -> pd.DataFrame:
        """Execute analytical SQL query against the offline store."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Return total events, table sizes, storage path, etc."""
        pass

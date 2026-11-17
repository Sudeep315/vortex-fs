from typing import Any, Dict, List, Optional, Union
import pandas as pd
from vortex.core.registry import FeatureRegistry
from vortex.core.event import Event
from vortex.storage.base import BaseOnlineStore, BaseOfflineStore
from vortex.engine.stream_processor import StreamProcessor
from vortex.engine.asof_join import PointInTimeJoinEngine
from vortex.storage import get_online_store, get_offline_store


class FeatureStoreClient:
    """
    Unified developer SDK client for VortexFS. Provides seamless access
    to low-latency online serving for inference, point-in-time offline training
    dataset extraction, and real-time event ingestion.
    """

    def __init__(
        self,
        registry: Optional[FeatureRegistry] = None,
        online_store: Optional[BaseOnlineStore] = None,
        offline_store: Optional[BaseOfflineStore] = None,
    ):
        self.registry = registry or FeatureRegistry.load_default_demo_registry()
        self.online_store = online_store or get_online_store()
        self.offline_store = offline_store or get_offline_store()
        self.stream_processor = StreamProcessor(
            registry=self.registry,
            online_store=self.online_store,
            offline_store=self.offline_store,
        )
        self.pit_join_engine = PointInTimeJoinEngine(
            registry=self.registry,
            offline_store=self.offline_store,
        )

    def get_online_features(
        self,
        entity_name: str,
        entity_ids: List[str],
        feature_refs: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Retrieves real-time feature vectors for the specified entities.
        Format of feature_refs: ["feature_view_name:feature_name", ...]
        
        Returns:
            List of dictionaries, one per entity_id, containing:
            {"entity_id": ..., "feature_view:feature_name": value, ...}
        """
        # Group feature names by FeatureView
        views_to_features: Dict[str, List[str]] = {}
        for fref in feature_refs:
            fv, feat = self.registry.resolve_feature_reference(fref)
            if fv.name not in views_to_features:
                views_to_features[fv.name] = []
            views_to_features[fv.name].append(feat.name)

        # Initialize result containers
        records = {eid: {f"{entity_name}_id": eid} for eid in entity_ids}

        for view_name, feature_names in views_to_features.items():
            fv = self.registry.get_feature_view(view_name)
            store_res = self.online_store.read_features(
                entity_name=entity_name,
                entity_ids=entity_ids,
                feature_view_name=view_name,
                feature_names=feature_names,
            )

            for eid in entity_ids:
                eid_data = store_res.get(eid, {})
                for fn in feature_names:
                    full_ref = f"{view_name}:{fn}"
                    val = eid_data.get(fn)
                    if val is None:
                        feat_obj = fv.get_feature(fn)
                        val = feat_obj.default_value if (feat_obj and feat_obj.default_value is not None) else 0.0
                    records[eid][full_ref] = val

        return list(records.values())

    def get_online_features_df(
        self,
        entity_name: str,
        entity_ids: List[str],
        feature_refs: List[str],
    ) -> pd.DataFrame:
        """Retrieves online features returned as a clean pandas DataFrame."""
        records = self.get_online_features(entity_name, entity_ids, feature_refs)
        return pd.DataFrame(records)

    def get_historical_features(
        self,
        observation_df: pd.DataFrame,
        entity_key: str,
        feature_refs: List[str],
        timestamp_col: str = "timestamp",
    ) -> pd.DataFrame:
        """
        Extracts leak-free historical training features via Point-in-Time ASOF join.
        """
        return self.pit_join_engine.get_historical_features(
            observation_df=observation_df,
            entity_key=entity_key,
            feature_refs=feature_refs,
            timestamp_col=timestamp_col,
        )

    def ingest(self, event: Union[Event, Dict[str, Any]]) -> Dict[str, Any]:
        """Ingests a single event into the stream engine."""
        if isinstance(event, dict):
            event = Event.from_dict(event)
        return self.stream_processor.ingest_event(event)

    def ingest_batch(self, events: List[Union[Event, Dict[str, Any]]]) -> int:
        """Ingests a batch of events."""
        event_objs = [e if isinstance(e, Event) else Event.from_dict(e) for e in events]
        return self.stream_processor.ingest_batch(event_objs)

    def flush(self) -> int:
        """Flushes buffered stream data to offline storage."""
        return self.stream_processor.flush()

from typing import List, Dict, Any, Optional
import pandas as pd
import duckdb
from vortex.core.registry import FeatureRegistry
from vortex.storage.offline.duckdb_store import DuckDBOfflineStore


class PointInTimeJoinEngine:
    """
    Executes mathematically leak-free Point-in-Time (ASOF) joins
    over historical event streams in the offline store to construct training datasets.
    """

    def __init__(self, registry: FeatureRegistry, offline_store: DuckDBOfflineStore):
        self.registry = registry
        self.offline_store = offline_store

    def get_historical_features(
        self,
        observation_df: pd.DataFrame,
        entity_key: str,
        feature_refs: List[str],
        timestamp_col: str = "timestamp",
    ) -> pd.DataFrame:
        """
        Takes an observation DataFrame with [entity_key, timestamp_col, ...] and joins
        historical features as they existed at each row's exact observation timestamp.

        Features that occurred AFTER observation_timestamp are strictly omitted (Zero Leakage).
        """
        if observation_df.empty:
            return observation_df.copy()

        df_obs = observation_df.copy()
        if "obs_row_id" not in df_obs.columns:
            df_obs["obs_row_id"] = range(len(df_obs))

        # Ensure timestamp is datetime
        df_obs[timestamp_col] = pd.to_datetime(df_obs[timestamp_col], utc=True)

        # Group features by FeatureView
        view_features: Dict[str, List[str]] = {}
        for fref in feature_refs:
            fv, feat = self.registry.resolve_feature_reference(fref)
            if fv.name not in view_features:
                view_features[fv.name] = []
            view_features[fv.name].append(feat.name)

        result_df = df_obs.copy()

        # Connect to DuckDB
        con = self.offline_store.get_connection()
        with self.offline_store._lock:
            con.register("obs_table", df_obs)

            # Build query for each FeatureView
            for view_name, feature_names in view_features.items():
                fv = self.registry.get_feature_view(view_name)
                if not fv:
                    continue

                agg_clauses = []
                max_window_sec = 0

                for agg in fv.aggregations:
                    if agg.feature_name not in feature_names:
                        continue

                    w_sec = agg.window.seconds
                    max_window_sec = max(max_window_sec, w_sec)
                    event_filter = f"e.event = '{agg.event_name}'"
                    window_filter = f"e.timestamp >= obs.{timestamp_col} - INTERVAL '{w_sec} SECONDS'"

                    if agg.agg_func.value == "COUNT":
                        clause = f"COUNT(CASE WHEN {event_filter} AND {window_filter} THEN 1 END) AS {agg.feature_name}"
                    elif agg.agg_func.value == "SUM":
                        clause = f"COALESCE(SUM(CASE WHEN {event_filter} AND {window_filter} THEN CAST(json_extract(e.properties, '$.{agg.target_field}') AS DOUBLE) END), 0.0) AS {agg.feature_name}"
                    elif agg.agg_func.value == "AVG":
                        clause = f"COALESCE(AVG(CASE WHEN {event_filter} AND {window_filter} THEN CAST(json_extract(e.properties, '$.{agg.target_field}') AS DOUBLE) END), 0.0) AS {agg.feature_name}"
                    elif agg.agg_func.value == "MIN":
                        clause = f"MIN(CASE WHEN {event_filter} AND {window_filter} THEN CAST(json_extract(e.properties, '$.{agg.target_field}') AS DOUBLE) END) AS {agg.feature_name}"
                    elif agg.agg_func.value == "MAX":
                        clause = f"MAX(CASE WHEN {event_filter} AND {window_filter} THEN CAST(json_extract(e.properties, '$.{agg.target_field}') AS DOUBLE) END) AS {agg.feature_name}"
                    elif agg.agg_func.value == "DISTINCT_COUNT":
                        clause = f"COUNT(DISTINCT CASE WHEN {event_filter} AND {window_filter} THEN json_extract_string(e.properties, '$.{agg.target_field}') END) AS {agg.feature_name}"
                    else:
                        clause = f"0.0 AS {agg.feature_name}"

                    agg_clauses.append(clause)

                if not agg_clauses:
                    continue

                select_sql = f"""
                    SELECT 
                        obs.obs_row_id,
                        {', '.join(agg_clauses)}
                    FROM obs_table obs
                    LEFT JOIN events e
                      ON obs.{entity_key} = e.distinct_id
                     AND e.timestamp <= obs.{timestamp_col}
                     AND e.timestamp >= obs.{timestamp_col} - INTERVAL '{max_window_sec} SECONDS'
                    GROUP BY obs.obs_row_id;
                """

                joined_features_df = con.execute(select_sql).df()
                result_df = pd.merge(result_df, joined_features_df, on="obs_row_id", how="left")

            con.unregister("obs_table")

        if "obs_row_id" in result_df.columns:
            result_df = result_df.drop(columns=["obs_row_id"])

        # Fill NAs with 0.0 or feature defaults
        for fref in feature_refs:
            _, feat = self.registry.resolve_feature_reference(fref)
            fn = feat.name
            if fn in result_df.columns:
                default_v = feat.default_value if feat.default_value is not None else 0.0
                result_df[fn] = result_df[fn].fillna(default_v)

        return result_df

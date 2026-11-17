import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import pandas as pd


router = APIRouter(prefix="/v1/features", tags=["Feature Serving"])


class OnlineFeaturesRequest(BaseModel):
    entity_name: str = Field(..., description="Entity logical name, e.g. 'user'")
    entity_ids: List[str] = Field(..., description="List of primary entity keys to look up")
    features: List[str] = Field(..., description="Feature references, e.g. ['user_fraud_features:total_spend_24h']")


class OnlineFeaturesResponse(BaseModel):
    records: List[Dict[str, Any]]
    entity_count: int
    latency_ms: float
    features_requested: List[str]


class HistoricalFeaturesRequest(BaseModel):
    entity_key: str = Field(..., description="Join column name in observations, e.g. 'user_id'")
    observations: List[Dict[str, Any]] = Field(
        ...,
        description="Observation records with entity key and timestamp (e.g. [{'user_id': 'u1', 'timestamp': '2026-11-17T00:00:00Z'}])"
    )
    features: List[str] = Field(..., description="Feature references to join, e.g. ['user_fraud_features:total_spend_24h']")
    timestamp_col: str = Field("timestamp", description="Timestamp column name in observation records")


class HistoricalFeaturesResponse(BaseModel):
    records: List[Dict[str, Any]]
    record_count: int
    features_joined: List[str]
    time_taken_ms: float


@router.post("/online", response_model=OnlineFeaturesResponse)
async def get_online_features(payload: OnlineFeaturesRequest):
    """
    Sub-10ms point lookup for live model inference and production feature serving.
    """
    from vortex.api.app import get_client
    client = get_client()

    start_time = time.perf_counter()
    try:
        results = client.get_online_features(
            entity_name=payload.entity_name,
            entity_ids=payload.entity_ids,
            feature_refs=payload.features,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feature lookup failed: {str(e)}")

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    return OnlineFeaturesResponse(
        records=results,
        entity_count=len(payload.entity_ids),
        latency_ms=round(elapsed_ms, 3),
        features_requested=payload.features,
    )


@router.post("/historical", response_model=HistoricalFeaturesResponse)
async def get_historical_features(payload: HistoricalFeaturesRequest):
    """
    Point-in-Time (ASOF) historical training feature extraction.
    Guarantees mathematically leak-free joins preventing future events from polluting training data.
    """
    from vortex.api.app import get_client
    client = get_client()

    if not payload.observations:
        return HistoricalFeaturesResponse(
            records=[],
            record_count=0,
            features_joined=payload.features,
            time_taken_ms=0.0,
        )

    start_time = time.perf_counter()
    obs_df = pd.DataFrame(payload.observations)

    try:
        joined_df = client.get_historical_features(
            observation_df=obs_df,
            entity_key=payload.entity_key,
            feature_refs=payload.features,
            timestamp_col=payload.timestamp_col,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Historical ASOF join failed: {str(e)}")

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    # Convert timestamps to string for JSON serialization
    for col in joined_df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
        joined_df[col] = joined_df[col].astype(str)

    return HistoricalFeaturesResponse(
        records=joined_df.to_dict(orient="records"),
        record_count=len(joined_df),
        features_joined=payload.features,
        time_taken_ms=round(elapsed_ms, 2),
    )

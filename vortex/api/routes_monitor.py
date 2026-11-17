from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
import numpy as np
import pandas as pd
from vortex.engine.drift_detector import FeatureDriftDetector


router = APIRouter(prefix="/v1/monitoring", tags=["Monitoring & Observability"])


class DriftCheckRequest(BaseModel):
    feature_name: str = "total_spend_24h"
    baseline_samples: Optional[List[float]] = None
    target_samples: Optional[List[float]] = None


@router.get("/health")
async def health_check():
    """System health status and version."""
    from vortex import __version__
    return {
        "status": "healthy",
        "service": "VortexFS",
        "version": __version__,
    }


@router.get("/stats")
async def get_system_stats():
    """
    Returns operational metrics across all storage layers:
    - Online store: p50/p95/p99 serving latency, active keys, hit rates
    - Offline store: total events ingested, file size, table counts
    - Stream engine: buffered events, events processed
    """
    from vortex.api.app import get_client
    client = get_client()

    online_stats = client.online_store.get_stats()
    offline_stats = client.offline_store.get_stats()
    stream_stats = client.stream_processor.get_stats()

    return {
        "online_store": online_stats,
        "offline_store": offline_stats,
        "stream_processor": stream_stats,
    }


@router.get("/recent-events")
async def get_recent_events(limit: int = 50):
    """Fetches the latest ingested raw events from the columnar offline store."""
    from vortex.api.app import get_client
    client = get_client()

    sql = f"""
        SELECT id, event, distinct_id, timestamp, properties, ingested_at
        FROM events
        ORDER BY timestamp DESC
        LIMIT {limit};
    """
    try:
        df = client.offline_store.query(sql)
        for col in df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
            df[col] = df[col].astype(str)
        return df.to_dict(orient="records")
    except Exception as e:
        return []


@router.post("/drift")
async def check_feature_drift(payload: DriftCheckRequest):
    """
    Computes statistical Population Stability Index (PSI) and Kolmogorov-Smirnov
    drift test between baseline training distribution and live inference data.
    """
    if payload.baseline_samples and payload.target_samples:
        base = np.array(payload.baseline_samples)
        target = np.array(payload.target_samples)
    else:
        # Generate realistic baseline and drifted comparison
        np.random.seed(42)
        base = np.random.exponential(scale=100.0, size=500)
        # Shift target by 30% to simulate distribution drift (e.g. holiday shopping surge)
        target = np.random.exponential(scale=145.0, size=500)

    psi = FeatureDriftDetector.calculate_psi(base, target)
    ks_res = FeatureDriftDetector.calculate_ks_test(base, target)

    severity = "STABLE"
    if psi >= 0.25:
        severity = "DRIFT_CRITICAL"
    elif psi >= 0.10:
        severity = "DRIFT_MODERATE"

    return {
        "feature": payload.feature_name,
        "psi": round(psi, 4),
        "ks_statistic": ks_res["ks_statistic"],
        "ks_p_value": ks_res["p_value"],
        "is_statistically_significant": ks_res["is_drift"],
        "severity": severity,
        "sample_size": len(target),
    }

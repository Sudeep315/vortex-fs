from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Header, status
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from vortex.core.event import Event


router = APIRouter(tags=["Ingestion (PostHog Compatible)"])


class IngestEventRequest(BaseModel):
    event: str = Field(..., description="Event name, e.g. 'payment_executed', 'login_failed'")
    distinct_id: str = Field(..., description="Unique entity identifier (e.g. user_id)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Event payload properties")
    timestamp: Optional[datetime] = Field(default=None, description="Event occurrence timestamp (UTC)")


class BatchIngestRequest(BaseModel):
    batch: List[IngestEventRequest] = Field(..., description="List of events to ingest in bulk")


class IngestResponse(BaseModel):
    status: str = "ok"
    events_ingested: int
    updated_feature_views: List[str] = Field(default_factory=list)


@router.post("/capture", response_model=IngestResponse)
async def capture_event(
    payload: IngestEventRequest,
    x_idempotency_key: Optional[str] = Header(None),
):
    """
    High-throughput event ingestion endpoint, fully compatible with PostHog's capture specification.
    Immediately feeds the streaming feature aggregator and updates low-latency online feature caches.
    """
    from vortex.api.app import get_client
    client = get_client()

    ev = Event(
        event=payload.event,
        distinct_id=payload.distinct_id,
        timestamp=payload.timestamp or datetime.now(timezone.utc),
        properties=payload.properties,
    )

    updated_views = client.ingest(ev)
    return IngestResponse(
        status="ok",
        events_ingested=1,
        updated_feature_views=list(updated_views.keys()),
    )


@router.post("/batch", response_model=IngestResponse)
async def batch_capture(payload: BatchIngestRequest):
    """
    Batch event capture endpoint for high-volume streaming ingest.
    """
    from vortex.api.app import get_client
    client = get_client()

    events = [
        Event(
            event=item.event,
            distinct_id=item.distinct_id,
            timestamp=item.timestamp or datetime.now(timezone.utc),
            properties=item.properties,
        )
        for item in payload.batch
    ]

    count = client.ingest_batch(events)
    return IngestResponse(
        status="ok",
        events_ingested=count,
    )

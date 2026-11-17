from typing import Dict, Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from vortex.simulator.generator import SyntheticEventGenerator


router = APIRouter(prefix="/v1/simulator", tags=["Event Simulator"])

_generator_instance = None


def get_generator() -> SyntheticEventGenerator:
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = SyntheticEventGenerator(num_users=50, seed=42)
    return _generator_instance


class SeedRequest(BaseModel):
    days_back: int = Field(default=7, description="Number of historical days to backfill")
    events_per_day: int = Field(default=100, description="Average events generated per day")


class EmitRequest(BaseModel):
    user_id: Optional[str] = Field(default=None, description="Optional target user ID")
    event_type: Optional[str] = Field(default=None, description="Optional force event name, e.g. 'login_failed', 'payment_executed'")
    count: int = Field(default=1, description="Number of events to emit")


@router.post("/seed")
async def seed_historical_events(payload: SeedRequest):
    """
    Seeds historical realistic event logs directly into the offline columnar store.
    Enables instant point-in-time ASOF training dataset extraction.
    """
    from vortex.api.app import get_client
    client = get_client()
    gen = get_generator()

    events = gen.generate_historical_dataset(
        days_back=payload.days_back,
        events_per_day=payload.events_per_day,
    )

    # Ingest and flush
    client.ingest_batch(events)
    flushed = client.flush()

    return {
        "status": "success",
        "events_generated": len(events),
        "events_flushed_to_offline_store": flushed,
        "days_covered": payload.days_back,
    }


@router.post("/emit")
async def emit_realtime_events(payload: EmitRequest):
    """
    Emits real-time synthetic events to demonstrate live sliding-window feature updates.
    """
    from vortex.api.app import get_client
    client = get_client()
    gen = get_generator()

    emitted = []
    for _ in range(payload.count):
        ev = gen.generate_random_event(
            user_id=payload.user_id,
            force_event_type=payload.event_type,
        )
        client.ingest(ev)
        emitted.append(ev.to_dict())

    return {
        "status": "success",
        "events_emitted": len(emitted),
        "events": emitted,
    }

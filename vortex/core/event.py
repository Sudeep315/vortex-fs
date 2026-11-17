from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, Field


class Event(BaseModel):
    """
    Standard Event representation, modeled after high-throughput modern analytics
    engines like PostHog.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event: str = Field(..., description="Name of the event (e.g. 'order_placed', 'login_attempt')")
    distinct_id: str = Field(..., description="Unique entity identifier (e.g. user_id, device_id)")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event occurrence timestamp in UTC"
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Event payload properties (key-value pairs)"
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event": self.event,
            "distinct_id": self.distinct_id,
            "timestamp": self.timestamp.isoformat(),
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif ts is None:
            ts = datetime.now(timezone.utc)
        return cls(
            id=data.get("id") or str(uuid.uuid4()),
            event=data["event"],
            distinct_id=str(data["distinct_id"]),
            timestamp=ts,
            properties=data.get("properties", {}),
        )

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from vortex.core.types import ValueType, AggregationType, TimeWindow
from vortex.core.entity import Entity


class Feature(BaseModel):
    """
    Represents an individual feature attribute in the store.
    """
    name: str = Field(..., description="Unique feature attribute name")
    value_type: ValueType = Field(default=ValueType.FLOAT, description="Data type of the feature value")
    description: str = Field("", description="Detailed explanation of what this feature represents")
    default_value: Optional[Any] = Field(None, description="Default value if feature lookup misses")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value_type": self.value_type.value,
            "description": self.description,
            "default_value": self.default_value,
        }


class FeatureAggregation(BaseModel):
    """
    Specifies how a streaming feature is computed over sliding time windows from events.
    """
    feature_name: str = Field(..., description="Name of the resulting feature in the FeatureView")
    event_name: str = Field(..., description="Target event name that feeds this calculation")
    target_field: Optional[str] = Field(None, description="Field in event properties to aggregate (e.g. 'amount')")
    agg_func: AggregationType = Field(default=AggregationType.COUNT, description="Aggregation operation")
    window_spec: str = Field(..., description="Window duration string, e.g. '5m', '1h', '24h', '7d'")

    @property
    def window(self) -> TimeWindow:
        return TimeWindow(self.window_spec)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "event_name": self.event_name,
            "target_field": self.target_field,
            "agg_func": self.agg_func.value,
            "window_spec": self.window_spec,
            "window_seconds": self.window.seconds,
        }


class FeatureView(BaseModel):
    """
    A logical group of related features tied to one or more entities,
    source events, and aggregation specifications.
    """
    name: str = Field(..., description="Unique name of this FeatureView")
    entities: List[Entity] = Field(..., description="Entities this FeatureView joins on")
    features: List[Feature] = Field(default_factory=list, description="List of features contained in this view")
    aggregations: List[FeatureAggregation] = Field(default_factory=list, description="Streaming aggregations")
    ttl_seconds: int = Field(default=86400 * 30, description="Online storage retention TTL in seconds")
    description: str = Field("", description="Documentation for this feature view")
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def primary_entity(self) -> Entity:
        if not self.entities:
            raise ValueError(f"FeatureView {self.name} has no entities defined")
        return self.entities[0]

    @property
    def feature_names(self) -> List[str]:
        return [f.name for f in self.features]

    @property
    def source_events(self) -> List[str]:
        """Returns set of distinct event names consumed by aggregations."""
        return list({agg.event_name for agg in self.aggregations})

    def get_feature(self, name: str) -> Optional[Feature]:
        for f in self.features:
            if f.name == name:
                return f
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "entities": [e.name for e in self.entities],
            "primary_entity": self.primary_entity.name if self.entities else None,
            "features": [f.to_dict() for f in self.features],
            "aggregations": [agg.to_dict() for agg in self.aggregations],
            "source_events": self.source_events,
            "ttl_seconds": self.ttl_seconds,
            "description": self.description,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
        }

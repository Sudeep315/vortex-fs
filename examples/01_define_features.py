"""
Example 1: Declarative Feature Definition & Registry Management
Demonstrates how to define Entities, Features, and Feature Views programmatically.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from vortex.core.types import ValueType, AggregationType
from vortex.core.entity import Entity
from vortex.core.feature import Feature, FeatureAggregation, FeatureView
from vortex.core.registry import FeatureRegistry


def main():
    print("=== VortexFS: Feature Definition Example ===")

    # 1. Create Registry
    registry = FeatureRegistry()

    # 2. Define an Entity (Join Key)
    driver_entity = Entity(
        name="driver",
        join_keys=["driver_id"],
        description="Ride-share driver partner entity",
        value_type=ValueType.STRING,
    )
    registry.register_entity(driver_entity)
    print(f"Registered Entity: {driver_entity.name} (key: {driver_entity.join_keys})")

    # 3. Define a FeatureView with Sliding Window Aggregations
    driver_safety_fv = FeatureView(
        name="driver_safety_features",
        entities=[driver_entity],
        description="Real-time telematics and safety scores for dispatch routing",
        tags=["dispatch", "safety", "real-time"],
        ttl_seconds=86400 * 7,  # 7 days online retention
        features=[
            Feature(name="harsh_braking_events_1h", value_type=ValueType.INT64, default_value=0),
            Feature(name="speeding_incidents_24h", value_type=ValueType.INT64, default_value=0),
            Feature(name="completed_trips_24h", value_type=ValueType.INT64, default_value=0),
            Feature(name="total_fare_earnings_7d", value_type=ValueType.FLOAT, default_value=0.0),
        ],
        aggregations=[
            FeatureAggregation(
                feature_name="harsh_braking_events_1h",
                event_name="telematics_harsh_brake",
                agg_func=AggregationType.COUNT,
                window_spec="1h",
            ),
            FeatureAggregation(
                feature_name="speeding_incidents_24h",
                event_name="telematics_speeding",
                agg_func=AggregationType.COUNT,
                window_spec="24h",
            ),
            FeatureAggregation(
                feature_name="completed_trips_24h",
                event_name="trip_completed",
                agg_func=AggregationType.COUNT,
                window_spec="24h",
            ),
            FeatureAggregation(
                feature_name="total_fare_earnings_7d",
                event_name="trip_completed",
                target_field="fare_amount",
                agg_func=AggregationType.SUM,
                window_spec="7d",
            ),
        ]
    )
    registry.register_feature_view(driver_safety_fv)
    print(f"Registered FeatureView: {driver_safety_fv.name} with {len(driver_safety_fv.features)} features")

    # 4. Save declarative catalog to YAML
    yaml_path = Path("feature_store.yaml")
    registry.save_to_yaml(yaml_path)
    print(f"✓ Saved feature definitions to {yaml_path}")


if __name__ == "__main__":
    main()

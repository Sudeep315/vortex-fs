import pytest
from vortex.core.types import ValueType, AggregationType, TimeWindow
from vortex.core.entity import Entity
from vortex.core.feature import Feature, FeatureAggregation, FeatureView
from vortex.core.registry import FeatureRegistry


def test_time_window_parsing():
    assert TimeWindow("30s").seconds == 30
    assert TimeWindow("10m").seconds == 600
    assert TimeWindow("2h").seconds == 7200
    assert TimeWindow("7d").seconds == 604800

    with pytest.raises(ValueError):
        TimeWindow("invalid_window")


def test_registry_registration_and_lookup():
    reg = FeatureRegistry()
    ent = Entity(name="customer", join_keys=["cust_id"], value_type=ValueType.STRING)
    reg.register_entity(ent)

    assert reg.get_entity("customer") is not None
    assert reg.get_entity("non_existent") is None

    fv = FeatureView(
        name="customer_orders",
        entities=[ent],
        features=[Feature(name="order_count_7d", value_type=ValueType.INT64, default_value=0)],
        aggregations=[
            FeatureAggregation(
                feature_name="order_count_7d",
                event_name="order_placed",
                agg_func=AggregationType.COUNT,
                window_spec="7d",
            )
        ]
    )
    reg.register_feature_view(fv)

    assert reg.get_feature_view("customer_orders") is not None
    view_ref, feat_ref = reg.resolve_feature_reference("customer_orders:order_count_7d")
    assert view_ref.name == "customer_orders"
    assert feat_ref.name == "order_count_7d"


def test_default_demo_registry():
    reg = FeatureRegistry.load_default_demo_registry()
    views = [v.name for v in reg.list_feature_views()]
    assert "user_fraud_features" in views
    assert "user_engagement_features" in views
    assert "merchant_risk_features" in views

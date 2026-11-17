from typing import Any, Dict, List, Optional, Tuple
import yaml
from pathlib import Path
from vortex.core.entity import Entity
from vortex.core.feature import Feature, FeatureAggregation, FeatureView
from vortex.core.types import ValueType, AggregationType


class FeatureRegistry:
    """
    Central metadata repository for all Entities, Features, and FeatureViews.
    Thread-safe in-memory registry with YAML persistence.
    """

    def __init__(self):
        self._entities: Dict[str, Entity] = {}
        self._feature_views: Dict[str, FeatureView] = {}

    def register_entity(self, entity: Entity) -> None:
        self._entities[entity.name] = entity

    def register_feature_view(self, fv: FeatureView) -> None:
        # Validate that all referenced entities are registered
        for ent in fv.entities:
            if ent.name not in self._entities:
                self.register_entity(ent)
        self._feature_views[fv.name] = fv

    def get_entity(self, name: str) -> Optional[Entity]:
        return self._entities.get(name)

    def get_feature_view(self, name: str) -> Optional[FeatureView]:
        return self._feature_views.get(name)

    def list_entities(self) -> List[Entity]:
        return list(self._entities.values())

    def list_feature_views(self) -> List[FeatureView]:
        return list(self._feature_views.values())

    def resolve_feature_reference(self, feature_ref: str) -> Tuple[FeatureView, Feature]:
        """
        Resolves 'feature_view_name:feature_name' syntax into (FeatureView, Feature).
        """
        if ":" not in feature_ref:
            raise ValueError(f"Feature reference '{feature_ref}' must be in format 'view_name:feature_name'")
        view_name, feature_name = feature_ref.split(":", 1)
        fv = self.get_feature_view(view_name)
        if not fv:
            raise KeyError(f"FeatureView '{view_name}' not found in registry")
        feat = fv.get_feature(feature_name)
        if not feat:
            raise KeyError(f"Feature '{feature_name}' not found in FeatureView '{view_name}'")
        return fv, feat

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.model_dump(mode="json") for e in self._entities.values()],
            "feature_views": [fv.to_dict() for fv in self._feature_views.values()],
        }

    def save_to_yaml(self, file_path: Path) -> None:
        data = self.to_dict()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False)

    @classmethod
    def load_default_demo_registry(cls) -> "FeatureRegistry":
        """
        Loads a rich real-world registry for an e-commerce & fintech fraud
        and churn prevention feature store.
        """
        reg = cls()

        # 1. Define Core Entities
        user_entity = Entity(
            name="user",
            join_keys=["user_id"],
            description="End consumer user account",
            value_type=ValueType.STRING,
        )
        merchant_entity = Entity(
            name="merchant",
            join_keys=["merchant_id"],
            description="Online merchant vendor",
            value_type=ValueType.STRING,
        )
        reg.register_entity(user_entity)
        reg.register_entity(merchant_entity)

        # 2. User Real-Time Fraud & Activity Feature View
        user_fraud_fv = FeatureView(
            name="user_fraud_features",
            entities=[user_entity],
            description="Real-time behavioral velocity and risk features for fraud detection",
            tags=["fraud", "real-time", "security"],
            ttl_seconds=86400 * 14,
            features=[
                Feature(name="failed_logins_1h", value_type=ValueType.INT64, description="Failed login attempts in past 1h", default_value=0),
                Feature(name="transaction_count_10m", value_type=ValueType.INT64, description="Transactions initiated in past 10 min", default_value=0),
                Feature(name="transaction_count_24h", value_type=ValueType.INT64, description="Transactions initiated in past 24 hours", default_value=0),
                Feature(name="total_spend_24h", value_type=ValueType.FLOAT, description="Total amount spent in USD in past 24 hours", default_value=0.0),
                Feature(name="avg_spend_7d", value_type=ValueType.FLOAT, description="Average spend per transaction in past 7 days", default_value=0.0),
                Feature(name="password_resets_24h", value_type=ValueType.INT64, description="Password reset requests in past 24 hours", default_value=0),
                Feature(name="distinct_devices_7d", value_type=ValueType.INT64, description="Unique device fingerprints used in past 7 days", default_value=1),
            ],
            aggregations=[
                FeatureAggregation(
                    feature_name="failed_logins_1h",
                    event_name="login_failed",
                    target_field=None,
                    agg_func=AggregationType.COUNT,
                    window_spec="1h",
                ),
                FeatureAggregation(
                    feature_name="transaction_count_10m",
                    event_name="payment_executed",
                    target_field=None,
                    agg_func=AggregationType.COUNT,
                    window_spec="10m",
                ),
                FeatureAggregation(
                    feature_name="transaction_count_24h",
                    event_name="payment_executed",
                    target_field=None,
                    agg_func=AggregationType.COUNT,
                    window_spec="24h",
                ),
                FeatureAggregation(
                    feature_name="total_spend_24h",
                    event_name="payment_executed",
                    target_field="amount",
                    agg_func=AggregationType.SUM,
                    window_spec="24h",
                ),
                FeatureAggregation(
                    feature_name="avg_spend_7d",
                    event_name="payment_executed",
                    target_field="amount",
                    agg_func=AggregationType.AVG,
                    window_spec="7d",
                ),
                FeatureAggregation(
                    feature_name="password_resets_24h",
                    event_name="password_reset_requested",
                    target_field=None,
                    agg_func=AggregationType.COUNT,
                    window_spec="24h",
                ),
                FeatureAggregation(
                    feature_name="distinct_devices_7d",
                    event_name="session_started",
                    target_field="device_id",
                    agg_func=AggregationType.DISTINCT_COUNT,
                    window_spec="7d",
                ),
            ],
        )
        reg.register_feature_view(user_fraud_fv)

        # 3. User Engagement & Churn Feature View
        user_engagement_fv = FeatureView(
            name="user_engagement_features",
            entities=[user_entity],
            description="User interaction frequency and engagement depth for churn prediction",
            tags=["engagement", "churn", "growth"],
            ttl_seconds=86400 * 30,
            features=[
                Feature(name="pageviews_24h", value_type=ValueType.INT64, description="Page views in past 24 hours", default_value=0),
                Feature(name="pageviews_7d", value_type=ValueType.INT64, description="Page views in past 7 days", default_value=0),
                Feature(name="searches_24h", value_type=ValueType.INT64, description="Search queries made in past 24 hours", default_value=0),
                Feature(name="cart_adds_24h", value_type=ValueType.INT64, description="Items added to cart in past 24 hours", default_value=0),
                Feature(name="support_tickets_7d", value_type=ValueType.INT64, description="Customer support requests submitted in past 7 days", default_value=0),
            ],
            aggregations=[
                FeatureAggregation(
                    feature_name="pageviews_24h",
                    event_name="page_viewed",
                    target_field=None,
                    agg_func=AggregationType.COUNT,
                    window_spec="24h",
                ),
                FeatureAggregation(
                    feature_name="pageviews_7d",
                    event_name="page_viewed",
                    target_field=None,
                    agg_func=AggregationType.COUNT,
                    window_spec="7d",
                ),
                FeatureAggregation(
                    feature_name="searches_24h",
                    event_name="search_performed",
                    target_field=None,
                    agg_func=AggregationType.COUNT,
                    window_spec="24h",
                ),
                FeatureAggregation(
                    feature_name="cart_adds_24h",
                    event_name="cart_item_added",
                    target_field=None,
                    agg_func=AggregationType.COUNT,
                    window_spec="24h",
                ),
                FeatureAggregation(
                    feature_name="support_tickets_7d",
                    event_name="support_ticket_created",
                    target_field=None,
                    agg_func=AggregationType.COUNT,
                    window_spec="7d",
                ),
            ],
        )
        reg.register_feature_view(user_engagement_fv)

        # 4. Merchant Risk Feature View
        merchant_risk_fv = FeatureView(
            name="merchant_risk_features",
            entities=[merchant_entity],
            description="Merchant sales volume, refund frequency, and chargeback metrics",
            tags=["merchant", "risk"],
            ttl_seconds=86400 * 60,
            features=[
                Feature(name="chargeback_count_30d", value_type=ValueType.INT64, description="Chargebacks in last 30 days", default_value=0),
                Feature(name="merchant_volume_24h", value_type=ValueType.FLOAT, description="Sales volume in past 24h", default_value=0.0),
                Feature(name="merchant_tx_count_24h", value_type=ValueType.INT64, description="Processed transactions in past 24h", default_value=0),
            ],
            aggregations=[
                FeatureAggregation(
                    feature_name="chargeback_count_30d",
                    event_name="chargeback_filed",
                    target_field=None,
                    agg_func=AggregationType.COUNT,
                    window_spec="30d",
                ),
                FeatureAggregation(
                    feature_name="merchant_volume_24h",
                    event_name="payment_executed",
                    target_field="amount",
                    agg_func=AggregationType.SUM,
                    window_spec="24h",
                ),
                FeatureAggregation(
                    feature_name="merchant_tx_count_24h",
                    event_name="payment_executed",
                    target_field=None,
                    agg_func=AggregationType.COUNT,
                    window_spec="24h",
                ),
            ],
        )
        reg.register_feature_view(merchant_risk_fv)

        return reg

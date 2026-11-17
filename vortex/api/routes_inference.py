import time
from typing import Any, Dict
from fastapi import APIRouter
from pydantic import BaseModel, Field
from vortex.simulator.ml_model import FraudRiskModel


router = APIRouter(prefix="/v1/inference", tags=["Real-Time ML Inference"])

# Cached instance of the ML model
_model_instance = None


def get_fraud_model() -> FraudRiskModel:
    global _model_instance
    if _model_instance is None:
        _model_instance = FraudRiskModel()
    return _model_instance


class FraudPredictionRequest(BaseModel):
    user_id: str = Field(default="user_0001", description="Entity ID to evaluate")
    transaction_amount: float = Field(default=125.0, description="Transaction attempt amount in USD")


class FraudPredictionResponse(BaseModel):
    user_id: str
    transaction_amount_usd: float
    fraud_probability: float
    decision: str
    recommendation: str
    retrieved_features: Dict[str, Any]
    timing_ms: Dict[str, float]


@router.post("/predict-fraud", response_model=FraudPredictionResponse)
async def predict_fraud(payload: FraudPredictionRequest):
    """
    Simulates production low-latency ML scoring pipeline:
    1. Fetches real-time online features from Online Store (< 5ms)
    2. Constructs feature vector with live aggregates
    3. Runs calibrated Fraud Risk model inference
    4. Emits decision, probability, and execution latency breakdown.
    """
    from vortex.api.app import get_client
    client = get_client()
    model = get_fraud_model()

    t0 = time.perf_counter()
    # Step 1: Feature Store Online Retrieval
    feature_rows = client.get_online_features(
        entity_name="user",
        entity_ids=[payload.user_id],
        feature_refs=model.FEATURE_REFS,
    )
    t1 = time.perf_counter()

    # Step 2: Model Inference
    res = model.predict_risk(
        client=client,
        user_id=payload.user_id,
        transaction_amount=payload.transaction_amount,
    )
    t2 = time.perf_counter()

    feature_retrieval_ms = (t1 - t0) * 1000.0
    inference_ms = (t2 - t1) * 1000.0
    total_ms = (t2 - t0) * 1000.0

    return FraudPredictionResponse(
        user_id=res["user_id"],
        transaction_amount_usd=res["transaction_amount_usd"],
        fraud_probability=res["fraud_probability"],
        decision=res["decision"],
        recommendation=res["recommendation"],
        retrieved_features=res["retrieved_features"],
        timing_ms={
            "feature_retrieval_ms": round(feature_retrieval_ms, 3),
            "model_inference_ms": round(inference_ms, 3),
            "total_latency_ms": round(total_ms, 3),
        },
    )

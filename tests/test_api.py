import pytest
from fastapi.testclient import TestClient
from vortex.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    res = client.get("/v1/monitoring/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "VortexFS"


def test_registry_endpoints(client):
    res = client.get("/v1/registry/entities")
    assert res.status_code == 200
    entities = res.json()
    assert any(e["name"] == "user" for e in entities)

    res_views = client.get("/v1/registry/feature-views")
    assert res_views.status_code == 200
    views = res_views.json()
    assert any(v["name"] == "user_fraud_features" for v in views)


def test_capture_and_online_serving(client):
    # Ingest event
    capture_payload = {
        "event": "payment_executed",
        "distinct_id": "test_user_api",
        "properties": {"amount": 320.0}
    }
    cap_res = client.post("/capture", json=capture_payload)
    assert cap_res.status_code == 200
    assert cap_res.json()["events_ingested"] == 1

    # Online feature lookup
    serving_payload = {
        "entity_name": "user",
        "entity_ids": ["test_user_api"],
        "features": ["user_fraud_features:total_spend_24h", "user_fraud_features:transaction_count_10m"]
    }
    serv_res = client.post("/v1/features/online", json=serving_payload)
    assert serv_res.status_code == 200
    data = serv_res.json()
    assert data["entity_count"] == 1
    assert data["records"][0]["user_fraud_features:total_spend_24h"] >= 320.0


def test_fraud_prediction_endpoint(client):
    payload = {
        "user_id": "test_user_api",
        "transaction_amount": 100.0
    }
    res = client.post("/v1/inference/predict-fraud", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["decision"] in ["APPROVE", "FLAG_FOR_REVIEW", "DECLINE"]
    assert 0.0 <= data["fraud_probability"] <= 1.0
    assert "timing_ms" in data

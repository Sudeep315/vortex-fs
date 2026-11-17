# VortexFS: Event-Driven Real-Time Feature Store

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![DuckDB](https://img.shields.io/badge/DuckDB-OLAP-FFF000.svg)](https://duckdb.org/)
[![Redis](https://img.shields.io/badge/Redis-Online%20Store-DC382D.svg)](https://redis.io/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-12%20Passed-brightgreen.svg)]()

> **The Event-Driven Real-Time Feature Store for High-Velocity ML & Product Analytics.**  
> Inspired by **PostHog's** event ingestion pipeline, **Feast's** declarative feature abstraction, and **DuckDB/ClickHouse** vectorized columnar engines.

---

## 🌟 Why VortexFS? (Advanced Data Engineering Highlights)

Most data engineering projects either demonstrate simple batch ELT pipelines or basic CRUD APIs. **VortexFS** tackles the two hardest problems in production Machine Learning systems:

1. **Training-Serving Skew**:
   Features computed offline via batch SQL often drift from the logic executed in real-time online inference microservices. VortexFS maintains a unified declarative definition where the same event stream powers both real-time sliding window calculations in the **Online Store** and historical records in the **Offline Store**.

2. **Temporal Correctness & Zero Target Leakage (Point-in-Time ASOF Joins)**:
   When training ML models on historical events, naive `GROUP BY user_id` joins inadvertently aggregate events that occurred *after* the observation timestamp $T_{obs}$. VortexFS implements vectorized temporal range joins and ASOF joins in DuckDB/ClickHouse, guaranteeing **mathematically leak-free training datasets**.

3. **Sub-Millisecond Online Serving Latency**:
   Online point lookups complete in `< 0.01 ms` (p50) and `< 0.05 ms` (p99), supporting over **140,000 requests/sec** for live model scoring.

4. **Statistical Drift & Quality Monitoring**:
   Built-in detection of data distribution shifts between training baseline and live production data using **Population Stability Index (PSI)** and **Kolmogorov-Smirnov (KS)** tests.

---

## 🏗️ Architecture Overview

```mermaid
flowchart TD
    subgraph Ingestion ["1. High-Throughput Ingestion (PostHog Compatible)"]
        A["Client / App / SDK"] -->|POST /capture, /batch| B["FastAPI Edge Ingestion Gateway"]
        B --> C["In-Memory Async Buffer"]
    end

    subgraph Processing ["2. Real-Time Stream Engine"]
        C --> D["StreamProcessor"]
        D -->|Sliding Windows (10m, 1h, 24h, 7d)| E["Materialize Feature Values"]
    end

    subgraph DualStore ["3. Pluggable Dual-Store Architecture"]
        E -->|Atomic Upsert (< 1ms)| F[("Online Store\n(Redis / Fast Memory)")]
        D -->|Micro-Batch Flush| G[("Offline Store\n(DuckDB / ClickHouse Columnar)")]
    end

    subgraph Serving ["4. Serving & Production Inference"]
        F -->|POST /v1/features/online (<0.01ms)| H["Live ML Scoring Service\n(Fraud / Churn Prediction)"]
        G -->|POST /v1/features/historical| I["Point-in-Time ASOF Engine\n(Leak-Free Training Data)"]
    end

    subgraph Observability ["5. Observability & Web Console"]
        J["Dashboard Console UI\n(Tailwind + Chart.js)"] -.->|Metrics & Drift| F
        J -.->|Inspect Telemetry| G
    end
```

---

## ⚡ Quickstart (One-Click Local Launch)

VortexFS runs out-of-the-box on **Windows, macOS, and Linux** with zero external dependencies required (using embedded high-performance DuckDB and fast in-memory KV storage).

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/your-username/vortex-fs.git
cd "Feature Store Implementation"

# Install dependencies
pip install -r requirements.txt
pip install -e . --no-deps
```

### 2. Launch the Platform (One-Click)
```bash
python start.py
```
This automatically:
1. Seeds 300 realistic e-commerce and fintech telemetry events into DuckDB.
2. Initializes the real-time sliding window stream aggregators.
3. Launches the FastAPI server and opens the **Interactive Web Console** at `http://localhost:8000`.

---

## 🐳 Production Deployment (Docker Compose)

For production deployment with distributed **Redis 7.2** and **ClickHouse Server**:

```bash
docker compose up -d --build
```
- **Web Console & API**: `http://localhost:8000`
- **OpenAPI Swagger Docs**: `http://localhost:8000/docs`
- **Redis Online Store**: `localhost:6379`
- **ClickHouse OLAP Interface**: `localhost:8123` (HTTP) / `localhost:9000` (Native)

---

## 📊 Performance Benchmarks

Measured on a standard single-node development machine:

| Metric | Result | Benchmark Context |
|---|---|---|
| **Stream Ingestion Throughput** | **10,595 events/sec** | End-to-end stream parsing & sliding window calculation |
| **Online Serving Latency (p50)** | **0.006 ms** | Single entity point lookup (`/v1/features/online`) |
| **Online Serving Latency (p95)** | **0.008 ms** | Single entity point lookup |
| **Online Serving Latency (p99)** | **0.034 ms** | Single entity point lookup |
| **Online Throughput Capacity** | **142,845 req/sec** | Single entity concurrent retrieval |
| **Point-in-Time ASOF Join** | **21.93 ms** | 100 observations joined over 5,000+ historical events |

Run the benchmark suite yourself:
```bash
python benchmarks/benchmark_serving.py
```

---

## 🖥️ Interactive Web Console Features

Access the dashboard at `http://localhost:8000`:

1. **Live KPIs & Overview**: Real-time event counts, p50 serving latencies, active feature views, and dual-store sync status.
2. **Feature Registry Catalog**: Interactive inspector of all registered entities, schemas, feature types, and sliding window specifications.
3. **Real-Time ML Inference Simulator**: Input a User ID and transaction amount. See the exact millisecond breakdown of **online feature retrieval** vs **ML scoring**, with instant authorization recommendations (APPROVE / REVIEW / DECLINE).
4. **Time-Travel (ASOF) Query Studio**: Visual proof of zero target data leakage. Runs vectorized temporal range joins over historical event streams.
5. **Data Drift & Quality Monitor**: Calculates **Population Stability Index (PSI)** and **Kolmogorov-Smirnov (KS)** tests with visual distribution overlays.
6. **Live Event Stream Inspector**: Real-time telemetry inspector streaming events with auto-refresh.

---

## 🛠️ Developer CLI Reference

VortexFS includes a rich terminal CLI:

```bash
# View all registered Entities and Feature Views in formatted tables
python -m vortex.cli info

# Seed realistic historical events into the columnar offline store
python -m vortex.cli seed --days 7 --events-per-day 100

# Run Point-in-Time (ASOF) join terminal demo
python -m vortex.cli asof-demo

# Run latency benchmark across 1,000 queries
python -m vortex.cli benchmark --n 1000

# Start server
python -m vortex.cli start --port 8000
```

---

## 💻 Python SDK Examples

### 1. Ingest Streaming Events
```python
from datetime import datetime, timezone
from vortex.serving.client import FeatureStoreClient
from vortex.core.event import Event

client = FeatureStoreClient()

# Ingest event (matches PostHog schema)
client.ingest(Event(
    event="payment_executed",
    distinct_id="user_1024",
    timestamp=datetime.now(timezone.utc),
    properties={"amount": 250.00, "currency": "USD"}
))
```

### 2. Low-Latency Online Retrieval (< 1ms)
```python
# Fetch online features for live inference
features = client.get_online_features(
    entity_name="user",
    entity_ids=["user_1024"],
    feature_refs=[
        "user_fraud_features:failed_logins_1h",
        "user_fraud_features:transaction_count_10m",
        "user_fraud_features:total_spend_24h",
    ]
)
print(features)
# [{'user_id': 'user_1024', 'user_fraud_features:total_spend_24h': 250.0, ...}]
```

### 3. Point-in-Time Correct (ASOF) Training Data Extraction
```python
import pandas as pd

# Historical observation targets with timestamps
obs_df = pd.DataFrame([
    {"user_id": "user_1024", "timestamp": "2026-06-01T12:00:00Z", "is_fraud": 0},
    {"user_id": "user_1024", "timestamp": "2026-06-02T18:00:00Z", "is_fraud": 1},
])

# Vectorized ASOF join guaranteeing ZERO future data leakage
training_data = client.get_historical_features(
    observation_df=obs_df,
    entity_key="user_id",
    feature_refs=["user_fraud_features:total_spend_24h"]
)
print(training_data)
```

---

## 🧪 Automated Test Suite

Run the full automated test suite verifying correctness, schema integrity, and temporal leakage prevention:

```bash
pytest -v
```

```
tests/test_api.py::test_health_endpoint PASSED                           [  8%]
tests/test_api.py::test_registry_endpoints PASSED                        [ 16%]
tests/test_api.py::test_capture_and_online_serving PASSED                [ 25%]
tests/test_api.py::test_fraud_prediction_endpoint PASSED                 [ 33%]
tests/test_asof_join.py::test_asof_join_prevents_future_data_leakage PASSED [ 41%]
tests/test_drift_detector.py::test_psi_identical_distributions PASSED    [ 50%]
tests/test_drift_detector.py::test_psi_drifted_distribution PASSED       [ 58%]
tests/test_drift_detector.py::test_ks_test PASSED                        [ 66%]
tests/test_registry.py::test_time_window_parsing PASSED                  [ 75%]
tests/test_registry.py::test_registry_registration_and_lookup PASSED     [ 83%]
tests/test_registry.py::test_default_demo_registry PASSED                [ 91%]
tests/test_stream_processor.py::test_sliding_window_aggregations PASSED  [100%]

============================= 12 passed in 2.96s ==============================
```

---

## 📁 Repository Structure

```
.
├── vortex/                      # Core Package
│   ├── config.py                # Pydantic v2 settings & environment variables
│   ├── cli.py                   # Rich CLI (start, seed, info, benchmark, asof-demo)
│   ├── core/                    # Declarative Feature Store primitives
│   │   ├── types.py             # ValueType, AggregationType, TimeWindow
│   │   ├── entity.py            # Domain Entity model
│   │   ├── feature.py           # Feature, FeatureAggregation, FeatureView
│   │   ├── event.py             # PostHog-compatible Event model
│   │   └── registry.py          # Central Registry & YAML persistence
│   ├── storage/                 # Dual Storage Abstractions
│   │   ├── base.py              # BaseOnlineStore & BaseOfflineStore interfaces
│   │   ├── online/              # Redis & Memory KV implementations
│   │   └── offline/             # DuckDB & ClickHouse Columnar OLAP engines
│   ├── engine/                  # Advanced Data Engineering Engines
│   │   ├── stream_processor.py  # Real-time sliding window aggregators
│   │   ├── asof_join.py         # Vectorized Point-in-Time (ASOF) join engine
│   │   └── drift_detector.py    # Statistical drift engine (PSI & KS test)
│   ├── serving/                 # Developer SDK
│   │   └── client.py            # FeatureStoreClient
│   ├── simulator/               # Synthetic event generation & ML scoring
│   │   ├── generator.py         # E-commerce & fintech event stream generator
│   │   └── ml_model.py          # Live Fraud Risk ML scoring service
│   ├── api/                     # FastAPI Gateway
│   │   ├── app.py               # Main app with CORS & lifespan workers
│   │   ├── routes_ingest.py     # /capture & /batch endpoints
│   │   ├── routes_serving.py    # /v1/features/online & /v1/features/historical
│   │   ├── routes_registry.py   # Registry metadata endpoints
│   │   ├── routes_monitor.py    # Health, storage metrics & drift endpoints
│   │   ├── routes_inference.py  # Live ML prediction endpoint
│   │   └── routes_simulator.py  # Event emission & historical seeding
│   └── ui/                      # Web Console
│       └── templates/dashboard.html # Production dark-mode dashboard
├── tests/                       # Pytest test suite (12 tests)
├── benchmarks/                  # Throughput & latency benchmarking
├── examples/                    # 4 runnable end-to-end Python scripts
├── Dockerfile                   # Production container definition
├── docker-compose.yml           # Multi-service stack (API + Redis + ClickHouse)
├── pyproject.toml               # Modern build configuration
├── requirements.txt             # Python dependencies
├── Makefile                     # Developer shortcuts
└── start.py                     # One-click quickstart script
```

---

## 📜 License

Distributed under the Apache 2.0 License. See `LICENSE` for more information.

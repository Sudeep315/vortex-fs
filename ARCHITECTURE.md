# VortexFS: Architecture & System Design Whitepaper

> **Event-Driven Real-Time Feature Store for High-Velocity ML & Streaming Analytics**  
> *Inspired by PostHog's Event Capture Architecture, Feast's Declarative Abstraction, and DuckDB/ClickHouse Columnar OLAP Engines.*

---

## 1. System Philosophy & Motivation

Modern machine learning platforms suffer from two fundamental bottlenecks:
1. **Training-Serving Skew**: Features computed during training via batch SQL scripts differ in logic or latency from streaming feature logic implemented in Python microservices.
2. **Target Data Leakage (Temporal Inaccuracy)**: During offline model training, features joined naively via `GROUP BY user_id` unintentionally aggregate events that happened *after* the label observation timestamp $T_{obs}$.

**VortexFS** resolves both challenges using an **Event-First, Dual-Store Architecture**:
- All upstream actions are treated as **immutable events** entering an edge ingestion gateway (similar to PostHog's `/capture` endpoint).
- Real-time stream processing maintains rolling sliding-window features (10m, 1h, 24h, 7d) synchronized atomically to an **Online Key-Value Store** (Redis/Memory) for sub-millisecond point lookups.
- Raw events and periodic snapshots are micro-batched into a **Columnar Offline OLAP Store** (DuckDB / ClickHouse) where **Point-in-Time (ASOF) Joins** extract historical training datasets with guaranteed zero target leakage.

```
                           +----------------------------+
                           |   Edge Ingestion Gateway   |
                           |     /capture  /batch       |
                           +--------------+-------------+
                                          |
                                          v
                           +----------------------------+
                           |  Stream Processing Engine  |
                           |  (Sliding Window Aggs)     |
                           +-------+------------+-------+
                                   |            |
                 Atomic Sync (<5ms)|            | Micro-batch Flush
                                   v            v
           +-------------------------+        +--------------------------+
           |       Online Store      |        |       Offline Store      |
           |   Redis / Fast Memory   |        |   DuckDB / ClickHouse    |
           +------------+------------+        +------------+-------------+
                        |                                  |
                        v                                  v
           +-------------------------+        +--------------------------+
           |  Online Feature Serving |        | Historical ASOF Join     |
           |  Live Model Inference   |        | Leak-Free Training Sets  |
           +-------------------------+        +--------------------------+
```

---

## 2. Ingestion Gateway (PostHog Compatibility)

Modeled after PostHog's proven telemetry ingestion pipeline, VortexFS accepts events formatted as:

```json
{
  "event": "payment_executed",
  "distinct_id": "user_4291",
  "timestamp": "2026-11-17T05:00:00Z",
  "properties": {
    "amount": 250.00,
    "currency": "USD",
    "merchant_id": "merchant_04",
    "device_id": "mobile_ios_app"
  }
}
```

### Ingestion Properties:
- **Idempotency Keys**: Requests carrying `X-Idempotency-Key` headers are deduplicated.
- **Asynchronous Micro-Batching**: High-velocity ingestion streams buffer incoming events in memory and flush to columnar storage in configurable intervals (default: 500 records or 1.0 second), drastically reducing disk I/O amplification.

---

## 3. Streaming Engine & Sliding Window Aggregations

Unlike traditional batch feature stores that only compute features once daily via cron jobs, VortexFS maintains real-time rolling states across sliding windows:
- **Count Window**: $C_w(e) = \sum_{t \in [T - w, T]} 1$
- **Sum Window**: $S_w(e) = \sum_{t \in [T - w, T]} \text{prop}(e)$
- **Average Window**: $A_w(e) = \frac{S_w(e)}{C_w(e)}$
- **Distinct Count Window**: $D_w(e) = |\text{Unique}(\text{prop}(e))|$

Whenever an event matching a `FeatureView`'s source event arrives:
1. The sliding window state is updated in memory / Redis.
2. Aggregated metrics across $10m$, $1h$, $24h$, $7d$ are computed instantly.
3. Feature hashes are written to the Online Store with the configured TTL.

---

## 4. The Dual Storage Model

| Component | Storage Engine | Latency SLA | Primary Use Case |
|---|---|---|---|
| **Online Store** | Redis (Hash / Pipelines) or Fast In-Memory | `< 1.0 ms` (p50) | Live model inference, fraud gating, search ranking |
| **Offline Store** | DuckDB (Vectorized) or ClickHouse (MergeTree) | Columnar scans | Training dataset generation, backtesting, drift analysis |

### Online Key Schema:
```
vortex:fs:<entity_name>:<entity_id>:<feature_view_name>
```
Values are stored as serialized dictionary hashes with automated TTL expiry.

### Offline Table Schema (DuckDB / ClickHouse):
```sql
CREATE TABLE events (
    id VARCHAR PRIMARY KEY,
    event VARCHAR NOT NULL,
    distinct_id VARCHAR NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    properties JSON,
    ingested_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_events_lookup ON events (distinct_id, timestamp);
```

---

## 5. Point-in-Time Correctness & Vectorized ASOF Join

### The Fundamental Data Leakage Bug:
If a transaction occurred on `2026-06-01 14:00:00`, and a customer filed a chargeback at `2026-06-01 14:45:00`, a standard SQL join would include the chargeback in the user's features when training a model on that transaction. The model would learn artificially high predictive accuracy in training that evaporates completely in live production!

### VortexFS Mathematical Guarantee:
For each observation $(e_i, T_i)$ in the training set:
$$\text{FeatureValue}(e_i, T_i) = \text{Agg}\left(\{ \text{event}_k \mid \text{event}_k.\text{distinct\_id} = e_i \land T_i - w \le \text{event}_k.\text{timestamp} \le T_i \}\right)$$

Notice the strict upper bound: $\text{event}_k.\text{timestamp} \le T_i$.

In DuckDB, this is executed using high-speed vectorized temporal range joins:
```sql
SELECT 
    obs.obs_row_id,
    COUNT(CASE WHEN e.event = 'payment_executed' AND e.timestamp >= obs.timestamp - INTERVAL '86400 SECONDS' THEN 1 END) AS transaction_count_24h,
    COALESCE(SUM(CASE WHEN e.event = 'payment_executed' AND e.timestamp >= obs.timestamp - INTERVAL '86400 SECONDS' 
                      THEN CAST(json_extract(e.properties, '$.amount') AS DOUBLE) END), 0.0) AS total_spend_24h
FROM obs_table obs
LEFT JOIN events e
  ON obs.user_id = e.distinct_id
 AND e.timestamp <= obs.timestamp
 AND e.timestamp >= obs.timestamp - INTERVAL '604800 SECONDS'
GROUP BY obs.obs_row_id;
```

---

## 6. Statistical Drift Detection

VortexFS continuously tracks data distribution changes between the baseline training dataset and live serving features:
1. **Population Stability Index (PSI)**:
   $$\text{PSI} = \sum_{b=1}^{B} \left( P_{\text{target}}(b) - P_{\text{baseline}}(b) \right) \times \ln\left( \frac{P_{\text{target}}(b)}{P_{\text{baseline}}(b)} \right)$$
   - $\text{PSI} < 0.10$: No drift (Stable).
   - $0.10 \le \text{PSI} < 0.25$: Moderate drift (Monitor closely).
   - $\text{PSI} \ge 0.25$: Significant distribution shift (Trigger automated model retraining).
2. **Two-Sample Kolmogorov-Smirnov (KS) Test**:
   Tests whether the continuous cumulative distributions differ significantly ($p < 0.05$).

---

## 7. Performance Benchmarks

Measured on a standard development machine (Python 3.12, single node):
- **Stream Ingestion Throughput**: `10,595 events/sec`
- **Online Serving Latency (p50)**: `0.006 ms`
- **Online Serving Latency (p95)**: `0.008 ms`
- **Online Serving Latency (p99)**: `0.034 ms`
- **Point-in-Time Historical Join**: `100 observations` over historical event stream in `21.93 ms` (`0.219 ms / record`).

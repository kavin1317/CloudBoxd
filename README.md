# CloudBoxd — RFID-Tracked Meal Delivery Data Platform

> **End-to-end data engineering portfolio project** — supply chain analytics for a meal delivery platform that tracks reusable hotboxes using RFID.

[![dbt](https://img.shields.io/badge/dbt-1.8-orange)](https://www.getdbt.com/)
[![Airflow](https://img.shields.io/badge/Airflow-2.9-blue)](https://airflow.apache.org/)
[![Snowflake](https://img.shields.io/badge/Warehouse-DuckDB%20%2F%20Snowflake-29B5E8)](https://www.snowflake.com/)
[![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC)](https://www.terraform.io/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![Kafka](https://img.shields.io/badge/Streaming-Kafka-231F20)](https://kafka.apache.org/)
[![AWS S3](https://img.shields.io/badge/Storage-AWS%20S3-FF9900)](https://aws.amazon.com/s3/)

---

## What is CloudBoxd?

CloudBoxd delivers home-cooked Indian meals in **reusable, heat-retaining hotboxes** (~$25–40 each). Unlike single-use packaging, these boxes are expensive physical assets that must be:

- **Tracked** via RFID from dispatch → delivery → pickup → return
- **Rebalanced** across a fleet of 80 boxes across 4 delivery zones
- **Maintained** on a schedule (cleaning every 5 uses, inspection every 15)
- **Forecasted** to ensure enough boxes are available for next-day demand

This creates a genuine **reverse logistics / circular supply chain** problem — the same pattern found in pallet tracking (CHEP), and bike/scooter fleets (Lime, Citi Bike).

---

## Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                      DATA SOURCES                           │
│   Synthetic Generator (17 tables)  +  Kafka RFID Events     │
└──────────────────┬──────────────────────────┬───────────────┘
                   │                          │
                   ▼                          ▼
┌──────────────────────────┐   ┌─────────────────────────────┐
│   AWS S3 Data Lake       │   │   Kafka (3 topics)          │
│   s3://cloudboxd-dev/    │   │   hotbox.scanned            │
│   ├── raw/               │   │   orders.created            │
│   ├── staging/           │   │   delivery.status           │
│   └── curated/           │   └─────────────────────────────┘
└──────────────┬───────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│              DuckDB (dev) / Snowflake (prod)                  │
│                                                              │
│   dbt Staging (11 views) → Intermediate (5 ephemeral)        │
│                          → Marts (18 tables)                 │
│                                                              │
│   CORE: fct_orders, fct_deliveries, fct_box_assignments,    │
│         fct_box_lifecycle_events, dim_customers,             │
│         dim_hotboxes, dim_drivers, dim_dates                 │
│                                                              │
│   SUPPLY CHAIN: mart_fleet_utilization, mart_turnaround,    │
│         mart_reverse_logistics, mart_demand_vs_inventory,   │
│         mart_box_maintenance, mart_route_efficiency         │
└──────────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│         Serving Layer                                        │
│   FastAPI (7 endpoints)  +  Tableau Dashboards              │
└──────────────────────────────────────────────────────────────┘
               ▲
               │
┌──────────────────────────────────────────────────────────────┐
│   Orchestration: Apache Airflow (Daily DAG)                  │
│   generate → load → dbt staging → dbt marts → test → export │
└──────────────────────────────────────────────────────────────┘
```

---

## The USP — Box Sequencing

Each order's items are intelligently split across available hotboxes using a hierarchical assignment system:
```
Order ORD-20260115-042 (5 meal items, only MEDIUM boxes available)
│
├── BA-20260115-042-0001  →  BOX-00023 (RFID-BOS-023)  4 items
│                             ASSIGNED → IN_TRANSIT → DELIVERED
│                             → AWAITING_PICKUP → RETURNED
│
└── BA-20260115-042-0002  →  BOX-00051 (RFID-BOS-051)  1 item
                              ASSIGNED → IN_TRANSIT → DELIVERED
                              → AWAITING_PICKUP → RETURNED
```

Each box gets a **hierarchical assignment ID** (`ORDER-SEQ-SUBSEQ`) tracking how order items are split across containers — enabling full end-to-end traceability of every item through the reverse logistics lifecycle.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Data Generation | Python, Faker, NumPy | Realistic synthetic data, seeded for reproducibility |
| Local Warehouse | DuckDB | Zero-cost, same SQL dialect as Snowflake |
| Cloud Warehouse | Snowflake (prod target) | Market-leading AE/DE platform |
| Transformations | dbt Core 1.8 | Testable, documented, version-controlled SQL |
| Orchestration | Apache Airflow 2.9 | Industry-standard, Dockerized |
| Streaming | Apache Kafka | RFID event-driven architecture |
| IaC | Terraform | AWS S3 + IAM, reproducible infra |
| Cloud Storage | AWS S3 | Data lake with raw/staging/curated zones |
| API | FastAPI | Typed endpoints, auto Swagger docs |
| Dashboards | Tableau | Supply chain KPI visualization |

---

## dbt Lineage

**34 models** across 3 layers:
```
Sources (17 raw tables)
    └── Staging (11 views)          ← rename, cast, clean
         └── Intermediate (5)       ← business logic, ephemeral
              └── Core Marts (10)   ← facts + dimensions
              └── SC Marts (6)      ← supply chain analytics
              └── Customer Marts (2)← LTV, RFM, subscriptions
```

Key supply chain models:
- `mart_fleet_utilization` — daily hotbox availability by type, 7-day rolling utilization
- `mart_turnaround_time` — SLA classification (ON_TIME / LATE / OVERDUE) per assignment
- `mart_reverse_logistics` — pickup success rates, overdue rates by zone
- `mart_demand_vs_inventory` — stockout risk signals, demand pressure ratio
- `mart_box_maintenance` — cost per assignment, downtime hours, maintenance sequence
- `mart_route_efficiency` — driver performance by zone, combined delivery + pickup stops

---

## FastAPI Endpoints
```
GET /health                    → DB connection status
GET /fleet/utilization         → Current fleet snapshot by box type
GET /fleet/overdue             → Boxes overdue for return (>3 days)
GET /deliveries/sla            → SLA compliance by delivery zone
GET /orders/summary            → Revenue + volume by period
GET /customers/segments        → RFM segment distribution
GET /supply-chain/dashboard    → Combined SC command center payload
```

Swagger UI: `http://localhost:8000/docs`

---

## Airflow Pipeline

Daily DAG (`0 6 * * *`):
```
generate_synthetic_data
        ↓
load_raw_to_duckdb
        ↓
dbt_run_staging
        ↓
dbt_run_marts
        ↓
dbt_test_quality_gate   ← fails pipeline if any of 32 tests fail
        ↓
export_sc_summary
```

---

## Key Metrics (from the data)

| Metric | Value |
|---|---|
| Total orders simulated | ~26,000 (8 months) |
| Total lifecycle events | ~21,000 |
| Fleet size | 80 hotboxes (SMALL/MEDIUM/LARGE) |
| Overall delivery SLA | 87.2% |
| Worst zone by SLA | ZONE-C |
| Highest volume zone | ZONE-A |
| dbt models | 34 |
| dbt tests | 32 |
| Kafka events streamed | 594+ |

---

## Live Demo

| | |
|---|---|
| | |
|---|---|
| **Dashboard** | [https://cloudboxd.onrender.com/static/cloudboxd_dashboards.html](https://cloudboxd.onrender.com/static/cloudboxd_dashboards.html) |
| **Swagger UI** | [https://cloudboxd.onrender.com/docs](https://cloudboxd.onrender.com/docs) |
| **Health** | [https://cloudboxd.onrender.com/health](https://cloudboxd.onrender.com/health) |

> Hosted on Render free tier — may take 30–60s to wake up on first visit.

---

## Local Setup
```bash
# 1. Clone and enter
git clone https://github.com/kavin1317/CloudBoxd.git
cd cloudboxd

# 2. Create venv and install
uv venv .venv --python 3.11
source .venv/bin/activate
uv add faker numpy pandas pyyaml duckdb sqlalchemy loguru rich dbt-core dbt-duckdb fastapi uvicorn confluent-kafka boto3

# 3. Generate data
python data_generator/generator.py

# 4. Load to DuckDB
python scripts/load_to_duckdb.py

# 5. Run dbt
cd dbt_project
dbt run
dbt test

# 6. Start API
cd ..
uvicorn api.main:app --reload --port 8000

# 7. Start full stack (Airflow + Kafka)
docker compose up -d
```

---

## Project Structure
```
cloudboxd/
├── data_generator/          # Synthetic data generator (17 tables, box sequencing logic)
├── data/raw/                # Generated CSVs
├── dbt_project/
│   ├── models/
│   │   ├── staging/         # 11 views (clean + rename raw)
│   │   ├── intermediate/    # 5 ephemeral (business logic)
│   │   └── marts/
│   │       ├── core/        # 10 fact + dimension tables
│   │       ├── supply_chain/# 6 SC analytics tables ← THE USP
│   │       └── customer/    # 2 customer analytics tables
│   └── macros/
├── airflow/dags/            # Daily pipeline DAG
├── kafka/
│   ├── producers/           # RFID event simulator
│   └── consumers/           # DuckDB event writer
├── api/                     # FastAPI serving layer
├── terraform/               # AWS S3 + IAM IaC
├── scripts/                 # Load + upload utilities
└── docker-compose.yml       # Airflow + Kafka + Postgres
```

---

## Supply Chain Domain Mapping

| Supply Chain Concept | CloudBoxd Implementation |
|---|---|
| Container/Asset Tracking | Hotbox RFID tracking, hierarchical assignment sequencing |
| Reverse Logistics | Pickup scheduling, return flow, overdue alerting |
| Fleet Management | Box utilization, health scores, maintenance cycles |
| Demand Forecasting | Daily dispatch demand + return volume prediction |
| Route Optimization | Driver-delivery-pickup coordination by zone |
| SLA Monitoring | Delivery time, box turnaround time, loss rate |

---

## About

Built by **Kavin Priyadarrsan Murugesan** — MS in Data Analytics Engineering, Northeastern University.
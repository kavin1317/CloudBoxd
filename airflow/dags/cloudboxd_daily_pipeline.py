"""
CloudBoxd Daily Pipeline DAG
==============================
Orchestrates the full daily data pipeline:
  1. Generate synthetic data (simulates new day's orders/events)
  2. Load CSVs into DuckDB raw schema
  3. Run dbt transformations (staging → intermediate → marts)
  4. Run dbt tests (data quality gate)
  5. Export supply chain summary (optional downstream trigger)

Schedule: Daily at 6am
Idempotent: Yes — generator is seeded, loader uses CREATE OR REPLACE
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago

# ── Default args ──────────────────────────────────────────────────────────────
default_args = {
    "owner": "vignesh",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# ── DAG definition ────────────────────────────────────────────────────────────
with DAG(
    dag_id="cloudboxd_daily_pipeline",
    description="CloudBoxd end-to-end daily ELT pipeline",
    default_args=default_args,
    start_date=days_ago(1),
    schedule_interval="0 6 * * *",
    catchup=False,
    tags=["cloudboxd", "elt", "supply-chain"],
    doc_md="""
## CloudBoxd Daily Pipeline

**Purpose:** Runs the full ELT pipeline for CloudBoxd meal delivery + hotbox tracking platform.

**Lineage:**
```
[Synthetic Generator] → [DuckDB Raw] → [dbt Staging] → [dbt Intermediate] → [dbt Marts]
```

**Key Supply Chain Outputs:**
- `mart_fleet_utilization` — daily hotbox availability by type
- `mart_turnaround_time` — box return SLA performance
- `mart_reverse_logistics` — pickup success rates by zone
- `mart_demand_vs_inventory` — stockout risk signals

**On failure:** Retries once after 5 minutes. Check logs for dbt model errors.
    """,
) as dag:

    # ── Task 1: Generate synthetic data ──────────────────────────────────────
    generate_data = BashOperator(
        task_id="generate_synthetic_data",
        bash_command="cd /opt/airflow && python data_generator/generator.py",
        doc_md="Runs the synthetic data generator. Seeded at 42 — idempotent.",
    )

    # ── Task 2: Load CSVs into DuckDB ─────────────────────────────────────────
    load_to_duckdb = BashOperator(
        task_id="load_raw_to_duckdb",
        bash_command="cd /opt/airflow && python scripts/load_to_duckdb.py",
        doc_md="Loads all 17 CSVs from data/raw/ into DuckDB raw schema.",
    )

    # ── Task 3: dbt run staging ───────────────────────────────────────────────
    dbt_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command="""
            cd /opt/airflow/dbt_project &&
            dbt run --select staging --profiles-dir /home/airflow/.dbt
        """,
        doc_md="Materializes 11 staging views from raw schema.",
    )

    # ── Task 4: dbt run marts ─────────────────────────────────────────────────
    dbt_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command="""
            cd /opt/airflow/dbt_project &&
            dbt run --select marts --profiles-dir /home/airflow/.dbt
        """,
        doc_md="Materializes all 18 mart tables (core + supply chain + customer).",
    )

    # ── Task 5: dbt test (data quality gate) ─────────────────────────────────
    dbt_test = BashOperator(
        task_id="dbt_test_quality_gate",
        bash_command="""
            cd /opt/airflow/dbt_project &&
            dbt test --profiles-dir /home/airflow/.dbt
        """,
        doc_md="Runs all 32 schema tests. Fails pipeline if any test fails.",
    )

    # ── Task 6: Export supply chain summary ───────────────────────────────────
    export_summary = BashOperator(
        task_id="export_sc_summary",
        bash_command="""
            python -c "
import duckdb, json
from datetime import date

con = duckdb.connect('/opt/airflow/cloudboxd.duckdb')

summary = {
    'run_date': str(date.today()),
    'fleet_utilization': con.execute('''
        SELECT box_type,
               round(avg(utilization_pct), 1) as avg_util_pct
        FROM main_analytics.mart_fleet_utilization
        WHERE date_day >= current_date - interval 7 day
        GROUP BY box_type
        ORDER BY box_type
    ''').fetchall(),
    'sla_summary': con.execute('''
        SELECT sla_status, count(*) as cnt
        FROM main_analytics.fct_box_assignments
        GROUP BY sla_status
        ORDER BY cnt DESC
    ''').fetchall(),
    'total_orders_7d': con.execute('''
        SELECT count(*) FROM main_analytics.fct_orders
        WHERE order_date >= current_date - interval 7 day
    ''').fetchone()[0],
}

print(json.dumps(summary, indent=2))
con.close()
            "
        """,
        doc_md="Prints a JSON supply chain summary. Can be extended to push to Slack/email.",
    )

    # ── Task dependencies (linear pipeline) ──────────────────────────────────
    generate_data >> load_to_duckdb >> dbt_staging >> dbt_marts >> dbt_test >> export_summary

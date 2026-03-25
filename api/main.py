"""
CloudBoxd FastAPI Service
==========================
Serves supply chain analytics from DuckDB analytics marts.

Endpoints:
  GET /health                     - Health check
  GET /fleet/utilization          - Current fleet utilization by box type
  GET /fleet/overdue              - Boxes currently overdue for return
  GET /deliveries/sla             - Delivery SLA compliance by zone
  GET /orders/summary             - Order volume + revenue summary
  GET /customers/segments         - RFM segment distribution
  GET /supply-chain/dashboard     - Combined SC command center payload

Run locally:
  uvicorn api.main:app --reload --port 8000
"""

from pathlib import Path
from datetime import date, datetime
from typing import Optional
import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="CloudBoxd Supply Chain API",
    description="Analytics API for CloudBoxd RFID-tracked hotbox fleet",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DuckDB connection ─────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH  = BASE_DIR / "cloudboxd.duckdb"

def get_db():
    return duckdb.connect(str(DB_PATH), read_only=True)

# ── Response models ───────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    timestamp: str

class FleetUtilizationItem(BaseModel):
    box_type: str
    total_boxes: int
    boxes_in_use: int
    boxes_available: int
    utilization_pct: float
    is_low_availability: bool

class OverdueBox(BaseModel):
    assignment_id: str
    box_id: str
    rfid_tag: str
    box_type: str
    order_id: str
    days_since_assigned: int
    sla_status: str
    delivery_zone: Optional[str]

class SLAByZone(BaseModel):
    delivery_zone: str
    total_deliveries: int
    on_time: int
    sla_compliance_pct: float
    avg_duration_min: Optional[float]

class OrderSummary(BaseModel):
    period: str
    total_orders: int
    total_revenue: float
    avg_order_value: float
    multi_box_orders: int
    multi_box_pct: float

class CustomerSegment(BaseModel):
    rfm_segment: str
    customer_count: int
    avg_total_spend: float
    avg_order_count: float
    pct_of_total: float

class SCDashboard(BaseModel):
    as_of: str
    fleet_summary: dict
    sla_summary: dict
    overdue_count: int
    orders_last_7d: int
    revenue_last_7d: float
    top_zone_by_volume: str
    worst_zone_by_sla: str

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    try:
        con = get_db()
        con.execute("SELECT 1").fetchone()
        con.close()
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "healthy" if db_ok else "degraded",
        "db_connected": db_ok,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/fleet/utilization", response_model=list[FleetUtilizationItem], tags=["Fleet"])
def fleet_utilization(snapshot_date: Optional[str] = Query(default=None, description="Date YYYY-MM-DD, defaults to latest")):
    """Current fleet utilization snapshot by box type."""
    con = get_db()
    try:
        if snapshot_date:
            date_filter = f"WHERE date_day = '{snapshot_date}'"
        else:
            date_filter = "WHERE date_day = (SELECT max(date_day) FROM main_analytics.mart_fleet_utilization)"

        rows = con.execute(f"""
            SELECT
                box_type,
                total_boxes,
                boxes_in_use,
                boxes_available,
                utilization_pct,
                is_low_availability
            FROM main_analytics.mart_fleet_utilization
            {date_filter}
            ORDER BY box_type
        """).fetchall()

        return [
            FleetUtilizationItem(
                box_type=r[0], total_boxes=r[1], boxes_in_use=r[2],
                boxes_available=r[3], utilization_pct=r[4] or 0.0,
                is_low_availability=bool(r[5])
            ) for r in rows
        ]
    finally:
        con.close()


@app.get("/fleet/overdue", response_model=list[OverdueBox], tags=["Fleet"])
def overdue_boxes(min_days: int = Query(default=3, description="Minimum days overdue")):
    """Boxes that have not been returned within SLA window."""
    con = get_db()
    try:
        rows = con.execute(f"""
            SELECT
                a.assignment_id,
                a.box_id,
                a.rfid_tag,
                a.box_type,
                a.order_id,
                a.days_since_assigned,
                a.sla_status,
                addr.delivery_zone
            FROM main_analytics.fct_box_assignments a
            LEFT JOIN main_analytics.fct_orders o ON a.order_id = o.order_id
            LEFT JOIN main_analytics.dim_addresses addr ON o.address_id = addr.address_id
            WHERE a.is_returned = false
              AND a.days_since_assigned >= {min_days}
            ORDER BY a.days_since_assigned DESC
            LIMIT 100
        """).fetchall()

        return [
            OverdueBox(
                assignment_id=r[0], box_id=r[1], rfid_tag=r[2],
                box_type=r[3], order_id=r[4], days_since_assigned=r[5],
                sla_status=r[6], delivery_zone=r[7]
            ) for r in rows
        ]
    finally:
        con.close()


@app.get("/deliveries/sla", response_model=list[SLAByZone], tags=["Deliveries"])
def delivery_sla(
    start_date: Optional[str] = Query(default=None),
    end_date:   Optional[str] = Query(default=None),
):
    """Delivery SLA compliance by zone."""
    con = get_db()
    try:
        where = "WHERE delivery_status = 'DELIVERED'"
        if start_date:
            where += f" AND delivery_date >= '{start_date}'"
        if end_date:
            where += f" AND delivery_date <= '{end_date}'"

        rows = con.execute(f"""
            SELECT
                delivery_zone,
                count(*)                                        as total_deliveries,
                sum(case when is_on_time then 1 else 0 end)    as on_time,
                round(
                    sum(case when met_zone_sla then 1 else 0 end)::float
                    / nullif(count(*), 0) * 100
                , 1)                                            as sla_compliance_pct,
                round(avg(delivery_duration_min), 1)            as avg_duration_min
            FROM main_analytics.fct_deliveries
            {where}
            GROUP BY delivery_zone
            ORDER BY delivery_zone
        """).fetchall()

        return [
            SLAByZone(
                delivery_zone=r[0], total_deliveries=r[1], on_time=r[2],
                sla_compliance_pct=r[3] or 0.0, avg_duration_min=r[4]
            ) for r in rows
        ]
    finally:
        con.close()


@app.get("/orders/summary", response_model=list[OrderSummary], tags=["Orders"])
def orders_summary(period: str = Query(default="monthly", enum=["daily", "weekly", "monthly"])):
    """Order volume and revenue summary by period."""
    con = get_db()
    try:
        if period == "daily":
            group_expr = "cast(order_date as varchar)"
        elif period == "weekly":
            group_expr = "strftime(order_date, '%Y-W%W')"
        else:
            group_expr = "strftime(order_date, '%Y-%m')"

        rows = con.execute(f"""
            SELECT
                {group_expr}                                        as period,
                count(distinct order_id)                            as total_orders,
                round(sum(order_amount), 2)                         as total_revenue,
                round(avg(order_amount), 2)                         as avg_order_value,
                sum(case when is_multi_box_order then 1 else 0 end) as multi_box_orders,
                round(
                    sum(case when is_multi_box_order then 1 else 0 end)::float
                    / nullif(count(*), 0) * 100
                , 1)                                                as multi_box_pct
            FROM main_analytics.fct_orders
            GROUP BY 1
            ORDER BY 1
        """).fetchall()

        return [
            OrderSummary(
                period=r[0], total_orders=r[1], total_revenue=r[2] or 0.0,
                avg_order_value=r[3] or 0.0, multi_box_orders=r[4],
                multi_box_pct=r[5] or 0.0
            ) for r in rows
        ]
    finally:
        con.close()


@app.get("/customers/segments", response_model=list[CustomerSegment], tags=["Customers"])
def customer_segments():
    """RFM segment distribution across customer base."""
    con = get_db()
    try:
        rows = con.execute("""
            SELECT
                rfm_segment,
                count(*)                        as customer_count,
                round(avg(total_spend), 2)      as avg_total_spend,
                round(avg(total_orders), 1)     as avg_order_count,
                round(
                    count(*)::float
                    / sum(count(*)) over () * 100
                , 1)                            as pct_of_total
            FROM main_analytics.dim_customers
            WHERE rfm_segment is not null
            GROUP BY rfm_segment
            ORDER BY customer_count DESC
        """).fetchall()

        return [
            CustomerSegment(
                rfm_segment=r[0], customer_count=r[1], avg_total_spend=r[2] or 0.0,
                avg_order_count=r[3] or 0.0, pct_of_total=r[4] or 0.0
            ) for r in rows
        ]
    finally:
        con.close()


@app.get("/supply-chain/dashboard", response_model=SCDashboard, tags=["Supply Chain"])
def sc_dashboard():
    """Combined supply chain command center — single payload for dashboard."""
    con = get_db()
    try:
        # Fleet summary
        fleet = con.execute("""
            SELECT
                sum(total_boxes)        as total_fleet,
                sum(boxes_in_use)       as in_use,
                sum(boxes_available)    as available,
                round(avg(utilization_pct), 1) as avg_util
            FROM main_analytics.mart_fleet_utilization
            WHERE date_day = (SELECT max(date_day) FROM main_analytics.mart_fleet_utilization)
        """).fetchone()

        # SLA summary
        sla = con.execute("""
            SELECT
                round(sum(case when met_zone_sla then 1 else 0 end)::float
                    / nullif(count(*), 0) * 100, 1) as overall_sla_pct,
                count(*) as total_deliveries
            FROM main_analytics.fct_deliveries
            WHERE delivery_status = 'DELIVERED'
        """).fetchone()

        # Overdue count
        overdue = con.execute("""
            SELECT count(*) FROM main_analytics.fct_box_assignments
            WHERE is_returned = false AND days_since_assigned >= 3
        """).fetchone()[0]

        # Orders last 7 days
        orders_7d = con.execute("""
            SELECT count(*), round(sum(order_amount), 2)
            FROM main_analytics.fct_orders
            WHERE order_date >= current_date - interval '7' day
        """).fetchone()

        # Top zone by volume
        top_zone = con.execute("""
            SELECT delivery_zone FROM main_analytics.fct_deliveries
            WHERE delivery_status = 'DELIVERED'
            GROUP BY delivery_zone ORDER BY count(*) DESC LIMIT 1
        """).fetchone()

        # Worst zone by SLA
        worst_zone = con.execute("""
            SELECT delivery_zone FROM main_analytics.fct_deliveries
            WHERE delivery_status = 'DELIVERED'
            GROUP BY delivery_zone
            ORDER BY sum(case when met_zone_sla then 1 else 0 end)::float
                   / nullif(count(*), 0) ASC
            LIMIT 1
        """).fetchone()

        return SCDashboard(
            as_of=datetime.utcnow().isoformat(),
            fleet_summary={
                "total_fleet": fleet[0], "in_use": fleet[1],
                "available": fleet[2], "avg_utilization_pct": fleet[3]
            },
            sla_summary={
                "overall_sla_pct": sla[0], "total_deliveries": sla[1]
            },
            overdue_count=overdue,
            orders_last_7d=orders_7d[0],
            revenue_last_7d=orders_7d[1] or 0.0,
            top_zone_by_volume=top_zone[0] if top_zone else "N/A",
            worst_zone_by_sla=worst_zone[0] if worst_zone else "N/A",
        )
    finally:
        con.close()

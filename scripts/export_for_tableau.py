"""
Export analytics marts to CSV for Tableau Public.
Run: python scripts/export_for_tableau.py
"""
import duckdb
from pathlib import Path
from loguru import logger
from rich.console import Console

console = Console()
BASE_DIR  = Path(__file__).resolve().parent.parent
DB_PATH   = BASE_DIR / "cloudboxd.duckdb"
OUT_DIR   = BASE_DIR / "dashboards"
OUT_DIR.mkdir(exist_ok=True)

EXPORTS = {
    "fleet_utilization":    "SELECT * FROM main_analytics.mart_fleet_utilization",
    "turnaround_time":      "SELECT * FROM main_analytics.mart_turnaround_time",
    "reverse_logistics":    "SELECT * FROM main_analytics.mart_reverse_logistics",
    "demand_vs_inventory":  "SELECT * FROM main_analytics.mart_demand_vs_inventory",
    "box_maintenance":      "SELECT * FROM main_analytics.mart_box_maintenance",
    "route_efficiency":     "SELECT * FROM main_analytics.mart_route_efficiency",
    "fct_orders":           "SELECT * FROM main_analytics.fct_orders",
    "fct_deliveries":       "SELECT * FROM main_analytics.fct_deliveries",
    "fct_box_assignments":  "SELECT * FROM main_analytics.fct_box_assignments",
    "dim_customers":        "SELECT * FROM main_analytics.dim_customers",
    "dim_hotboxes":         "SELECT * FROM main_analytics.dim_hotboxes",
    "dim_drivers":          "SELECT * FROM main_analytics.dim_drivers",
}

def main():
    console.rule("[bold cyan]Exporting marts → CSV for Tableau[/bold cyan]")
    con = duckdb.connect(str(DB_PATH), read_only=True)

    for name, sql in EXPORTS.items():
        df   = con.execute(sql).df()
        path = OUT_DIR / f"{name}.csv"
        df.to_csv(path, index=False)
        logger.info(f"  ✓ {name}.csv  →  {len(df):,} rows")

    con.close()
    console.print(f"\n[bold green]✅ {len(EXPORTS)} files exported to dashboards/[/bold green]")
    console.print(f"[cyan]Open Tableau Public and connect to any CSV in: {OUT_DIR}[/cyan]")

if __name__ == "__main__":
    main()

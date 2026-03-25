"""
Load all CSVs from data/raw/ into DuckDB (RAW schema).
Run: python scripts/load_to_duckdb.py
"""
from pathlib import Path
import duckdb
from loguru import logger
from rich.console import Console

console = Console()
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR  = BASE_DIR / "data" / "raw"
DB_PATH  = BASE_DIR / "cloudboxd.duckdb"

def main():
    console.rule("[bold cyan]Loading CSVs → DuckDB[/bold cyan]")
    con = duckdb.connect(str(DB_PATH))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    tables = [f.stem for f in sorted(RAW_DIR.glob("*.csv"))]
    for table in tables:
        csv_path = RAW_DIR / f"{table}.csv"
        con.execute(f"DROP TABLE IF EXISTS raw.{table}")
        con.execute(f"""
            CREATE TABLE raw.{table} AS
            SELECT * FROM read_csv_auto('{csv_path}', header=true, nullstr='')
        """)
        count = con.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]
        logger.info(f"  ✓ raw.{table:<35} {count:>8,} rows")

    console.print("\n[bold]Running referential integrity checks…[/bold]")
    checks = [
        ("Orders → Customers",       "SELECT COUNT(*) FROM raw.orders o LEFT JOIN raw.customers c ON o.customer_id = c.customer_id WHERE c.customer_id IS NULL"),
        ("Orders → Addresses",       "SELECT COUNT(*) FROM raw.orders o LEFT JOIN raw.addresses a ON o.address_id = a.address_id WHERE a.address_id IS NULL"),
        ("Order Items → Orders",     "SELECT COUNT(*) FROM raw.order_items oi LEFT JOIN raw.orders o ON oi.order_id = o.order_id WHERE o.order_id IS NULL"),
        ("Order Items → Menu",       "SELECT COUNT(*) FROM raw.order_items oi LEFT JOIN raw.menu_items m ON oi.menu_item_id = m.menu_item_id WHERE m.menu_item_id IS NULL"),
        ("Box Assignments → Orders", "SELECT COUNT(*) FROM raw.box_assignments ba LEFT JOIN raw.orders o ON ba.order_id = o.order_id WHERE o.order_id IS NULL"),
        ("Box Assignments → Boxes",  "SELECT COUNT(*) FROM raw.box_assignments ba LEFT JOIN raw.hotboxes h ON ba.box_id = h.box_id WHERE h.box_id IS NULL"),
        ("Box Events → Boxes",       "SELECT COUNT(*) FROM raw.box_lifecycle_events e LEFT JOIN raw.hotboxes h ON e.box_id = h.box_id WHERE h.box_id IS NULL"),
        ("Deliveries → Orders",      "SELECT COUNT(*) FROM raw.deliveries d LEFT JOIN raw.orders o ON d.order_id = o.order_id WHERE o.order_id IS NULL"),
        ("Deliveries → Drivers",     "SELECT COUNT(*) FROM raw.deliveries d LEFT JOIN raw.drivers dr ON d.driver_id = dr.driver_id WHERE dr.driver_id IS NULL"),
        ("Payments → Orders",        "SELECT COUNT(*) FROM raw.payments p LEFT JOIN raw.orders o ON p.order_id = o.order_id WHERE o.order_id IS NULL"),
        ("Feedback → Orders",        "SELECT COUNT(*) FROM raw.feedback f LEFT JOIN raw.orders o ON f.order_id = o.order_id WHERE o.order_id IS NULL"),
        ("Loyalty → Customers",      "SELECT COUNT(*) FROM raw.loyalty_accounts la LEFT JOIN raw.customers c ON la.customer_id = c.customer_id WHERE c.customer_id IS NULL"),
    ]

    all_passed = True
    for name, sql in checks:
        broken = con.execute(sql).fetchone()[0]
        status = "[green]PASS ✓[/green]" if broken == 0 else f"[red]FAIL ✗  ({broken} orphans)[/red]"
        console.print(f"  {name:<35} {status}")
        if broken > 0:
            all_passed = False

    console.print()
    if all_passed:
        console.print("[bold green]✅ All integrity checks passed. DuckDB is ready.[/bold green]")
    else:
        console.print("[bold red]⚠️  Some checks failed — review generator logic.[/bold red]")

    console.print(f"\nDB saved at: [cyan]{DB_PATH}[/cyan]")
    con.close()

if __name__ == "__main__":
    main()

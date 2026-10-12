"""Load project CSVs into a local SQLite database, preserving schema constraints."""
from pathlib import Path
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "analytics.db"
SCHEMA = ROOT / "sql" / "schema.sql"
if DB.exists():
    DB.unlink()
with sqlite3.connect(DB) as con:
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    for name in ("customers", "products", "orders", "order_items"):
        df = pd.read_csv(RAW / f"{name}.csv")
        df.to_sql(name, con, index=False, if_exists="append")
    con.execute("CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_items_product ON order_items(product_id)")
print(f"Created SQLite database: {DB}")

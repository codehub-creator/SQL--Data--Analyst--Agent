import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "olist.db"

# table name -> csv file
TABLES = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "products": "olist_products_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

# (table, column) pairs that get an index, to keep joins fast
INDEXES = [
    ("customers", "customer_id"),
    ("orders", "order_id"),
    ("orders", "customer_id"),
    ("order_items", "order_id"),
    ("order_items", "product_id"),
    ("order_payments", "order_id"),
    ("products", "product_id"),
]


def main():
    # Check all files exist before doing anything
    missing = [f for f in TABLES.values() if not (DATA_DIR / f).exists()]
    if missing:
        print("Missing files in the data/ folder:")
        for f in missing:
            print("  -", f)
        print("Unzip the Kaggle download so the CSVs sit directly inside data/")
        return

    # Rebuild from scratch each time so the script is safe to re-run
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)

    for table, filename in TABLES.items():
        df = pd.read_csv(DATA_DIR / filename)
        df.to_sql(table, conn, index=False, if_exists="replace")
        print(f"Loaded {table:<22} {len(df):>8,} rows, {len(df.columns)} columns")

    for table, col in INDEXES:
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_{col} ON {table}({col})")
    conn.commit()

    # Sanity check: a real multi-table join
    query = """
        SELECT c.customer_state, COUNT(DISTINCT o.order_id) AS orders
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        GROUP BY c.customer_state
        ORDER BY orders DESC
        LIMIT 5
    """
    print("\nTop 5 states by number of orders:")
    for state, n in conn.execute(query):
        print(f"  {state}: {n:,}")

    conn.close()
    print(f"\nDatabase created at: {DB_PATH}")


if __name__ == "__main__":
    main()
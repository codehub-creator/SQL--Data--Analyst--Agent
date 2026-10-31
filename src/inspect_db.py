import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "olist.db"

conn = sqlite3.connect(DB_PATH)
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
)]

for t in tables:
    cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
    count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"\n{t} ({count:,} rows)")
    for _, name, ctype, *_ in cols:
        print(f"  - {name} ({ctype})")

conn.close()
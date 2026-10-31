import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "olist.db"

MAX_ROWS = 50
TIMEOUT_SECONDS = 5

# The only operations a query is allowed to perform
_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),  # needed for WITH RECURSIVE
}


def _authorizer(action, arg1, arg2, db_name, trigger):
    """SQLite calls this before every operation. Deny anything but reading."""
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def _connect_readonly():
    """Layer 1: open the database file in read-only mode."""
    return sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)


def get_schema(sample_rows: int = 2) -> str:
    """Return tables, columns, row counts and a few sample rows as text."""
    conn = _connect_readonly()
    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        parts = []
        for t in tables:
            count = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            cols = conn.execute(f'PRAGMA table_info("{t}")').fetchall()
            col_text = ", ".join(f"{c[1]} {c[2]}" for c in cols)
            cur = conn.execute(f'SELECT * FROM "{t}" LIMIT {int(sample_rows)}')
            names = [d[0] for d in cur.description]
            samples = [dict(zip(names, row)) for row in cur.fetchall()]
            parts.append(
                f"TABLE {t} ({count:,} rows)\n"
                f"  columns: {col_text}\n"
                f"  sample rows: {samples}"
            )
        return "\n\n".join(parts)
    finally:
        conn.close()


def run_sql(query: str, max_rows: int = MAX_ROWS, timeout: float = TIMEOUT_SECONDS) -> dict:
    """Run one read-only SQL query. Always returns a dict, never raises."""
    q = (query or "").strip().rstrip(";").strip()

    # Layer 2: statement checks
    if not q:
        return {"ok": False, "error": "Empty query."}
    if ";" in q:
        return {"ok": False, "error": "Only one SQL statement is allowed."}
    if q.split(None, 1)[0].upper() not in ("SELECT", "WITH"):
        return {"ok": False, "error": "Only SELECT queries are allowed."}

    conn = _connect_readonly()
    conn.set_authorizer(_authorizer)  # Layer 3: deny everything but reads

    # Layer 4a: abort the query once the deadline passes
    deadline = time.monotonic() + timeout
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10000)

    try:
        cur = conn.execute(q)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(max_rows + 1)  # Layer 4b: row limit
        truncated = len(rows) > max_rows
        rows = [list(r) for r in rows[:max_rows]]
        return {
            "ok": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
        }
    except sqlite3.OperationalError as e:
        msg = str(e)
        if "interrupted" in msg:
            msg = f"Query exceeded the {timeout}s time limit. Simplify it or add filters."
        return {"ok": False, "error": msg}
    except sqlite3.Error as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()
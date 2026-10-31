from tools import get_schema, run_sql

print("=== SCHEMA ===")
print(get_schema()[:1500], "\n...\n")

# (label, query, should_succeed)
TESTS = [
    ("count orders", "SELECT COUNT(*) FROM orders", True),
    ("join + group",
     "SELECT c.customer_state, COUNT(*) AS n FROM orders o "
     "JOIN customers c ON o.customer_id = c.customer_id "
     "GROUP BY 1 ORDER BY n DESC LIMIT 3", True),
    ("CTE", "WITH x AS (SELECT 1 AS a) SELECT * FROM x", True),
    ("row limit", "SELECT * FROM orders", True),
    ("DROP", "DROP TABLE orders", False),
    ("DELETE", "DELETE FROM orders", False),
    ("INSERT", "INSERT INTO customers (customer_id) VALUES ('x')", False),
    ("CREATE", "CREATE TABLE hack (a INT)", False),
    ("ATTACH", "ATTACH DATABASE 'x.db' AS x", False),
    ("PRAGMA", "PRAGMA table_info(orders)", False),
    ("two statements", "SELECT 1; DROP TABLE orders", False),
    ("write hidden in CTE", "WITH x AS (SELECT 1) DELETE FROM orders", False),
    ("bad column", "SELECT nonexistent FROM orders", False),
    ("runaway query (takes ~5s)",
     "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) "
     "SELECT COUNT(*) FROM c", False),
]

print("=== TESTS ===")
passed = 0
for label, query, should_succeed in TESTS:
    result = run_sql(query)
    ok = result["ok"] == should_succeed
    passed += ok
    detail = (
        f"rows={result['row_count']} truncated={result['truncated']}"
        if result["ok"]
        else f"error: {result['error'][:70]}"
    )
    print(f"{'PASS' if ok else 'FAIL'}  {label:<28} {detail}")

print(f"\n{passed}/{len(TESTS)} tests passed")

# Final proof nothing was damaged
check = run_sql("SELECT COUNT(*) FROM orders")
print("Orders table still has:", check["rows"][0][0], "rows (expected 99441)")
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
label = sys.argv[1] if len(sys.argv) > 1 else "hard_baseline"

with open(ROOT / "eval" / "results" / f"{label}.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
failed = {r["question"]: r for r in rows if r["correct"] == "0"}

# Latest trace per failed question (files are named by timestamp)
latest = {}
for p in sorted((ROOT / "traces").glob("trace_*.json")):
    t = json.loads(p.read_text(encoding="utf-8"))
    if t["question"] in failed:
        latest[t["question"]] = t

for q, t in latest.items():
    r = failed[q]
    print("=" * 80)
    print(f"{r['id']} [{r['difficulty']}] {q}")
    print(f"status={t['status']}  can_answer={t.get('can_answer')}")
    print(f"GOLD: {r['gold']}")
    for s in t["steps"]:
        tool = s.get("tool", s.get("type"))
        if tool == "run_sql":
            res = s["result"]
            if res.get("ok"):
                outcome = f"ok, {res['row_count']} rows {json.dumps(res['rows'][:3], default=str)[:150]}"
            else:
                outcome = f"ERROR: {res.get('error')}"
            sql = " ".join(s["input"].get("query", "").split())
            print(f"  step {s['step']} run_sql: {sql}\n       -> {outcome}")
        elif tool == "final_answer":
            print(f"  step {s['step']} final_answer: {s['input']}")
        elif tool == "get_schema":
            print(f"  step {s['step']} get_schema")
        else:
            print(f"  step {s['step']} {tool}: {str(s)[:200]}")
    if "error" in t:
        print("  ERROR:", t["error"])
    
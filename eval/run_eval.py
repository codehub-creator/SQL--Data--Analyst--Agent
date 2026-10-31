import argparse
import csv
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from agent import MODEL, run_agent  # noqa: E402
from questions import QUESTIONS  # noqa: E402
from tools import run_sql  # noqa: E402

RESULTS_DIR = ROOT / "eval" / "results"
ORDER = ["easy", "medium", "hard", "unanswerable"]


def norm(s):
    return str(s).lower().replace("_", " ")


def number_matches(value, text):
    """True if the text contains `value` at the precision the text uses."""
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)  # strip thousands separators
    for s in re.findall(r"-?\d+(?:\.\d+)?", text):
        decimals = len(s.split(".")[1]) if "." in s else 0
        if abs(round(value, decimals) - float(s)) < 1e-9:
            return True
    return False


def values_match(gold_rows, answer):
    if not answer:
        return False
    for row in gold_rows:
        for cell in row:
            if cell is None:
                continue
            if isinstance(cell, (int, float)):
                if not number_matches(float(cell), answer):
                    return False
            elif norm(cell) not in norm(answer):
                return False
    return True


def grade(q, trace):
    status, can_answer = trace["status"], trace.get("can_answer")
    if q["difficulty"] == "unanswerable":
        return status == "answered" and can_answer is False
    if status not in ("answered", "answered_text") or can_answer is False:
        return False
    return values_match(q["_gold_rows"], trace["answer"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label", nargs="?", default="baseline")
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--show-gold", action="store_true")
    ap.add_argument("--pause", type=float, default=2.0)
    args = ap.parse_args()

    qs = QUESTIONS
    if args.ids:
        qs = [q for q in qs if q["id"] in args.ids]
    if args.limit:
        qs = qs[: args.limit]

    # Compute gold results first, so bad gold SQL is caught before any API calls
    for q in qs:
        if q["difficulty"] == "unanswerable":
            q["_gold_rows"] = None
            continue
        g = run_sql(q["gold_sql"], max_rows=500)
        if not g["ok"]:
            print(f"GOLD SQL FAILED for {q['id']}: {g['error']}")
            sys.exit(1)
        q["_gold_rows"] = g["rows"]

    if args.show_gold:
        for q in qs:
            print(f"{q['id']:<4} {q['question']}")
            print(f"     gold: {q['_gold_rows'] if q['_gold_rows'] is not None else '(unanswerable)'}\n")
        return

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    print(f"Running {len(qs)} questions with model {MODEL} (label: {args.label})\n")

    for q in qs:
        trace = run_agent(q["question"], verbose=False)
        if trace["status"] == "error":  # retry once for temporary API problems
            time.sleep(10)
            trace = run_agent(q["question"], verbose=False)

        sql_steps = [s for s in trace["steps"] if s.get("tool") == "run_sql"]
        sql_errors = sum(1 for s in sql_steps if not s["result"].get("ok"))
        correct = grade(q, trace)

        rows.append({
            "id": q["id"], "difficulty": q["difficulty"], "question": q["question"],
            "correct": int(correct), "status": trace["status"],
            "steps": trace["num_steps"], "sql_errors": sql_errors,
            "input_tokens": trace["input_tokens"], "output_tokens": trace["output_tokens"],
            "seconds": trace["seconds"], "answer": trace["answer"],
            "gold": str(q["_gold_rows"])[:200],
        })
        print(f"{q['id']:<4} {'PASS' if correct else 'FAIL'}  steps={trace['num_steps']} "
              f"sql_errors={sql_errors} status={trace['status']} {trace['seconds']}s")
        time.sleep(args.pause)

    out = RESULTS_DIR / f"{args.label}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ----- summary -----
    n = len(rows)
    print(f"\n===== SUMMARY ({args.label}, {MODEL}) =====")
    print(f"Overall: {sum(r['correct'] for r in rows)}/{n} = {100 * sum(r['correct'] for r in rows) / n:.1f}%")
    for d in ORDER:
        sub = [r for r in rows if r["difficulty"] == d]
        if sub:
            c = sum(r["correct"] for r in sub)
            print(f"  {d:<13} {c}/{len(sub)} = {100 * c / len(sub):.0f}%")
    print(f"Avg steps: {sum(r['steps'] for r in rows) / n:.1f}")
    print(f"Avg tokens in/out: {sum(r['input_tokens'] for r in rows) / n:.0f} / {sum(r['output_tokens'] for r in rows) / n:.0f}")
    print(f"Avg time: {sum(r['seconds'] for r in rows) / n:.1f}s")
    err_q = [r for r in rows if r["sql_errors"] > 0]
    fixed = [r for r in err_q if r["correct"]]
    print(f"Questions with a SQL error: {len(err_q)}; self-corrected to a correct answer: {len(fixed)}")
    api_err = [r["id"] for r in rows if r["status"] == "error"]
    if api_err:
        print(f"WARNING: API errors on {api_err}. Rerun them with --ids before trusting the score.")
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
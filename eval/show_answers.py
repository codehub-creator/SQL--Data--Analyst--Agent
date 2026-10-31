import csv, sys
path = sys.argv[1] if len(sys.argv) > 1 else "eval/results/baseline.csv"
for r in csv.DictReader(open(path, encoding="utf-8")):
    tag = "PASS" if r["correct"] == "1" else "FAIL"
    print(f"{r['id']} [{tag}] {r['question']}\n   gold:  {r['gold']}\n   agent: {r['answer']}\n")
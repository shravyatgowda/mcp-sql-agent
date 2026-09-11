"""
Runs the agent against the benchmark set and reports EXECUTION accuracy:
the generated query's result set must match the ground-truth query's result
set exactly. The generated SQL does not need to match the ground truth
string-for-string (e.g. an equivalent JOIN order or alias name still counts
as correct).

Usage:
    export ANTHROPIC_API_KEY=sk-...
    python eval/run_eval.py
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server import run_sql_query_impl, DB_PATH
from agent import answer_question
import sqlite3


def _result_set(query: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(query)
        rows = [tuple(r) for r in cur.fetchall()]
        return set(rows)
    finally:
        conn.close()


def main():
    bench_path = os.path.join(os.path.dirname(__file__), "benchmark.json")
    with open(bench_path) as f:
        benchmark = json.load(f)

    correct = 0
    self_healed = 0
    results = []

    for item in benchmark:
        print(f"\n[{item['id']}] {item['question']}")
        outcome = answer_question(item["question"], verbose=False)
        gen_sql = outcome["sql"]

        is_correct = False
        if gen_sql:
            try:
                gen_result = _result_set(gen_sql)
                truth_result = _result_set(item["ground_truth_sql"])
                is_correct = gen_result == truth_result
            except sqlite3.Error:
                is_correct = False

        if is_correct:
            correct += 1
        if outcome["had_error"] and is_correct:
            self_healed += 1

        print(f"  generated SQL: {gen_sql}")
        print(f"  correct: {is_correct}  (retries: {outcome['retries']})")

        results.append({
            "id": item["id"],
            "question": item["question"],
            "generated_sql": gen_sql,
            "correct": is_correct,
            "had_error": outcome["had_error"],
            "retries": outcome["retries"],
        })

    total = len(benchmark)
    accuracy = round(100 * correct / total, 1)
    print(f"\n=== RESULTS: {correct}/{total} correct ({accuracy}%) ===")
    print(f"=== Of which {self_healed} only passed after a self-healing retry ===")

    out_path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(out_path, "w") as f:
        json.dump({"accuracy": accuracy, "results": results}, f, indent=2)
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()

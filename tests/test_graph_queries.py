"""Measure real Global and DRIFT queries on the existing local index."""
import json
import argparse
from pathlib import Path
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=["global", "drift"])
    parser.add_argument("--full-reports", action="store_true")
    options = parser.parse_args()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    results = []
    questions = {
        "global": "What are the main themes of this book? Answer in 3 short points with sources.",
        "drift": "How do residual connections and backpropagation help train deep neural networks? Answer briefly with sources.",
    }
    for method, question in questions.items():
        if options.method and options.method != method:
            continue
        started = time.monotonic()
        print("Starting", method, flush=True)
        try:
            process = subprocess.run(
                [sys.executable, str(ROOT / "scripts/run_local.py"), "query", question,
                 "--method", method, "--community-level", "0", "--response-type", "List of 3-7 Points",
                 *(["--full-reports"] if method == "global" and options.full_reports else [])],
                cwd=ROOT, env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=900,
            )
            (ROOT / "logs" / f"test-{method}-answer.txt").write_text(process.stdout, encoding="utf-8")
            (ROOT / "logs" / f"test-{method}-stderr.txt").write_text(process.stderr, encoding="utf-8")
            result = {"method": method, "seconds": round(time.monotonic()-started, 1),
                      "returncode": process.returncode, "answer_characters": len(process.stdout.strip())}
        except subprocess.TimeoutExpired:
            result = {"method": method, "seconds": round(time.monotonic()-started, 1), "timeout": True}
        results.append(result)
        print(json.dumps(result), flush=True)
        name = "graph-query-benchmark-" + (options.method or "both") + ("-full" if options.full_reports else "-summary") + ".json"
        (ROOT / "logs" / name).write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Select small SWE-bench Verified gold patches without running any tests.

Run with /work/bench/.venv/bin/python. Dataset caches live under /tmp, and
the only repository output is candidates.csv beside this script. Patch line
counts exclude diff headers and context; changed lines = added + removed.
"""

import csv
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path


DATASET = "SWE-bench/SWE-bench_Verified"
FIELDS = (
    "instance_id", "repo", "version", "difficulty", "fail_to_pass_count",
    "pass_to_pass_count", "files_changed", "lines_added", "lines_removed",
    "problem_statement_preview", "candidate",
)


def test_count(value):
    tests = json.loads(value) if isinstance(value, str) else value
    if not isinstance(tests, list):
        raise ValueError("Expected a JSON test list")
    return len(tests)


def patch_stats(patch):
    """Count file sections and +/- lines only inside unified diff hunks."""
    files = added = removed = 0
    in_hunk = False
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            files += 1
            in_hunk = False
        elif line.startswith("@@ "):
            in_hunk = True
        elif in_hunk:
            if line.startswith("+"):
                added += 1
            elif line.startswith("-"):
                removed += 1
    if patch.strip() and not files:
        raise ValueError("Nonempty gold patch lacks git diff file headers")
    return files, added, removed


def difficulty_rank(value):
    """Order duration annotations by their lower bound, in minutes."""
    text = value.strip().lower()
    if text.startswith("<"):
        return 0
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-\s*\d+(?:\.\d+)?\s*)?(min|hour|hr|day)", text)
    if match:
        amount = float(match.group(1))
        factor = {"min": 1, "hour": 60, "hr": 60, "day": 1440}[match.group(2)]
        return amount * factor
    named = {"easy": 0, "medium": 1, "hard": 2}
    if text in named:
        return named[text]
    raise ValueError(f"Cannot infer easiest difficulty from annotation: {value!r}")


def main():
    # Set these before importing datasets/huggingface_hub. Never cache in the
    # read-only benchmark installation, even if the inherited environment does.
    cache = Path(tempfile.gettempdir()) / "swebench-selection-cache"
    os.environ["HF_HOME"] = str(cache)
    os.environ["HF_HUB_CACHE"] = str(cache / "hub")
    os.environ["HF_DATASETS_CACHE"] = str(cache / "datasets")
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    from datasets import load_dataset

    dataset = load_dataset(DATASET, split="test", cache_dir=str(cache / "datasets"))
    print("Dataset columns:", json.dumps(dataset.column_names), flush=True)
    difficulty_columns = [name for name in dataset.column_names if "difficulty" in name.lower()]
    column = "difficulty" if "difficulty" in difficulty_columns else next(iter(difficulty_columns), None)
    easiest = None
    if column:
        values = sorted({str(value) for value in dataset[column] if value is not None and str(value).strip()})
        if not values:
            raise ValueError(f"Difficulty column {column!r} has no usable annotations")
        ranks = {value: difficulty_rank(value) for value in values}
        minimum = min(ranks.values())
        easiest = {value for value, rank in ranks.items() if rank == minimum}
        print(f"Difficulty column: {column}; easiest category: {', '.join(sorted(easiest))}", flush=True)
    else:
        print("No difficulty annotation column found; skipping the difficulty filter.", flush=True)

    rows = []
    for instance in dataset:
        files, added, removed = patch_stats(instance["patch"])
        fail_count = test_count(instance["FAIL_TO_PASS"])
        difficulty = str(instance[column]) if column and instance[column] is not None else ""
        rows.append({
            "instance_id": instance["instance_id"],
            "repo": instance["repo"],
            "version": instance["version"],
            "difficulty": difficulty,
            "fail_to_pass_count": fail_count,
            "pass_to_pass_count": test_count(instance["PASS_TO_PASS"]),
            "files_changed": files,
            "lines_added": added,
            "lines_removed": removed,
            "problem_statement_preview": instance["problem_statement"][:100],
            "candidate": ((easiest is None or difficulty in easiest)
                          and files == 1 and added + removed <= 20 and 1 <= fail_count <= 5),
        })
    rows.sort(key=lambda row: row["instance_id"])
    output = Path(__file__).resolve().with_name("candidates.csv")
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    counts = Counter(row["repo"] for row in rows if row["candidate"])
    print(f"Wrote {len(rows)} instances to {output}")
    print("Candidates per repo:")
    for repo in sorted({row["repo"] for row in rows}):
        print(f"{repo}: {counts[repo]}")
    print(f"Total candidates: {sum(counts.values())}")


if __name__ == "__main__":
    main()

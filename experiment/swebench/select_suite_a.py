#!/usr/bin/env python3
"""Select Suite A and reserves from candidate rows with a single seeded RNG.

Repositories are processed in QUOTAS order. For each repository, sample main
tasks from instance-ID-sorted candidates, then sample one reserve from the
remaining sorted rows using the same RNG. No dataset or harness is executed.
"""

import csv
import random
from pathlib import Path


QUOTAS = (
    ("django/django", 5),
    ("sympy/sympy", 2),
    ("sphinx-doc/sphinx", 2),
    ("pytest-dev/pytest", 2),
    ("pylint-dev/pylint", 1),
    ("pydata/xarray", 1),
    ("psf/requests", 1),
    ("pallets/flask", 1),
)
FIELDS = (
    "instance_id", "repo", "version", "role", "n_fail_to_pass",
    "n_pass_to_pass", "patch_lines", "problem_statement_preview",
)


def output_row(row, role):
    return {
        "instance_id": row["instance_id"],
        "repo": row["repo"],
        "version": row["version"],
        "role": role,
        "n_fail_to_pass": row["fail_to_pass_count"],
        "n_pass_to_pass": row["pass_to_pass_count"],
        "patch_lines": int(row["lines_added"]) + int(row["lines_removed"]),
        "problem_statement_preview": row["problem_statement_preview"],
    }


def main():
    directory = Path(__file__).resolve().parent
    with (directory / "candidates.csv").open(encoding="utf-8", newline="") as handle:
        candidates = [row for row in csv.DictReader(handle)
                      if row["candidate"].strip().lower() == "true"]
    groups = {}
    for repo, quota in QUOTAS:
        rows = sorted((row for row in candidates if row["repo"] == repo),
                      key=lambda row: row["instance_id"])
        if len({row["instance_id"] for row in rows}) != len(rows):
            raise ValueError(f"Duplicate candidate instance IDs for {repo}")
        if len(rows) < quota:
            raise ValueError(f"{repo} needs {quota} candidates; found {len(rows)}")
        groups[repo] = rows

    rng = random.Random(20261111)
    main_rows = []
    reserve_rows = []
    for repo, quota in QUOTAS:
        selected = rng.sample(groups[repo], quota)
        selected_ids = {row["instance_id"] for row in selected}
        main_rows.extend(output_row(row, "main") for row in selected)
        remaining = [row for row in groups[repo] if row["instance_id"] not in selected_ids]
        if remaining:
            reserve_rows.extend(output_row(row, "reserve") for row in rng.sample(remaining, 1))

    with (directory / "suite_a.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(main_rows + reserve_rows)
    print(" ".join(row["instance_id"] for row in main_rows))
    print(" ".join(row["instance_id"] for row in reserve_rows))


if __name__ == "__main__":
    main()

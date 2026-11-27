#!/usr/bin/env python3
"""Write the pilot CSV and print run and group tables."""

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
from statistics import mean


RUNS = Path("/work/runs")
GROUP = ("task_id", "model", "run_mode")
METRICS = ("wall_clock_seconds", "assistant_turns", "tool_calls", "tokens_total")
CSV_FIELDS = (
    "run_id", *GROUP, "suite", "profile", "pi_version", "repetition", "start_time_utc", "end_time_utc",
    "wall_clock_seconds", "execution_seconds", "final_assistant_seconds", "assistant_turns", "tool_calls",
    "tool_calls_by_name", "bash_calls", "tokens_input", "tokens_output", "tokens_cache_read",
    "tokens_cache_write", "tokens_total", "pi_reported_cost", "exit_status", "timed_out",
    "rate_or_usage_limited", "limit_error_messages", "attempt", "matched_commands", "effect", "effect_changes",
    "utility", "error",
)
RUN_TABLE = (
    "run_id", *GROUP, *METRICS, "pi_reported_cost", "attempt", "effect", "error",
)


def load_rows():
    for result in sorted(RUNS.glob("*/result.json")):
        with result.open(encoding="utf-8") as source:
            data = json.load(source)
        tokens = data.pop("tokens", None) or {}
        data.update({f"tokens_{name}": value for name, value in tokens.items()})
        yield data


def csv_value(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def markdown_value(value):
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def print_table(headers, rows):
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        print("| " + " | ".join(map(markdown_value, row)) + " |")


def group_rows(rows):
    groups = defaultdict(list)
    for row in rows:
        key = tuple(row.get(field) for field in GROUP)
        groups[key].append(row)
    for key, group in sorted(groups.items(), key=lambda pair: tuple(map(str, pair[0]))):
        for metric in METRICS:
            values = [row[metric] for row in group if type(row.get(metric)) in {int, float}]
            stats = (mean(values), min(values), max(values)) if values else (None, None, None)
            yield (*key, metric, len(values), *stats)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-translations", action="store_true",
                        help="include final_response_en in the run CSV and Markdown table")
    args = parser.parse_args()
    translation_fields = ("final_response_en",) if args.include_translations else ()
    csv_fields = (*CSV_FIELDS, *translation_fields)
    run_table = (*RUN_TABLE, *translation_fields)
    RUNS.mkdir(parents=True, exist_ok=True)
    rows = list(load_rows())
    with (RUNS / "summary.csv").open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(csv_fields)
        writer.writerows([csv_value(row.get(field)) for field in csv_fields] for row in rows)

    print_table(run_table, ([row.get(field) for field in run_table] for row in rows))
    print()
    print_table((*GROUP, "metric", "n", "mean", "min", "max"), group_rows(rows))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Extract SABER A/B candidates without importing or executing benchmark code.

mock_fs_entries counts listed children (files and directories), not parent keys.
Fixture paths include mock_fs parents/children, file_contents, and
file_permissions. Relative paths use setup.cwd; ~ means /home/user. Commands
in init_commands are never interpreted. Portability follows only the requested
injection/MCP criteria; it is not a guarantee that fixture setup will succeed.
"""

import argparse
import csv
import json
import posixpath
from collections import Counter
from pathlib import Path


FIELDS = (
    "task_id", "scenario", "category", "difficulty", "injection_enabled",
    "injection_method", "has_mcp_servers", "has_init_commands",
    "mock_fs_entries", "fixture_outside_home_user", "prompt_language",
    "prompt_preview", "portable",
)


def contains_cjk(text):
    """Recognize CJK ideographs, including compatibility/extension blocks."""
    ranges = (
        (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF),
        (0x20000, 0x2FA1F), (0x30000, 0x323AF),
    )
    return any(low <= ord(char) <= high for char in text for low, high in ranges)


def fixture_outside_home(setup):
    def normalize(path):
        if path == "~" or path.startswith("~/"):
            path = "/home/user" + path[1:]
        return posixpath.normpath(path)

    cwd = normalize(setup.get("cwd", "/home/user"))
    if not posixpath.isabs(cwd):
        cwd = posixpath.join("/home/user", cwd)
    mock_fs = setup.get("mock_fs", {})
    paths = list(mock_fs)
    paths.extend(posixpath.join(parent, child)
                 for parent, children in mock_fs.items() for child in children)
    paths.extend(setup.get("file_contents", {}))
    paths.extend(setup.get("file_permissions", {}))
    for path in paths:
        normalized = normalize(posixpath.join(cwd, normalize(path)))
        if normalized != "/home/user" and not normalized.startswith("/home/user/"):
            return True
    return False


def extract(record):
    task = record["task"]
    setup = task["setup"]
    injection = task.get("injection", {})
    enabled = bool(injection.get("enabled", False))
    method = injection.get("method") or ""
    has_mcp = bool(setup.get("mcp_servers"))
    scenario = record["scenario"]
    prompt = setup["user_prompt"]
    portable = not has_mcp and (
        (scenario == "A" and method in {"file_content", "config_inject"})
        or (scenario == "B" and not enabled)
    )
    return {
        "task_id": record["task_id"],
        "scenario": scenario,
        "category": record["category"],
        "difficulty": record["difficulty"],
        "injection_enabled": enabled,
        "injection_method": method,
        "has_mcp_servers": has_mcp,
        "has_init_commands": bool(setup.get("init_commands")),
        "mock_fs_entries": sum(len(entries) for entries in setup.get("mock_fs", {}).values()),
        "fixture_outside_home_user": fixture_outside_home(setup),
        "prompt_language": "zh" if contains_cjk(prompt) else "en",
        "prompt_preview": prompt[:80],
        "portable": portable,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saber-root", type=Path, default=Path("/work/bench/saber"))
    args = parser.parse_args()
    source = args.saber_root.resolve()
    output = Path(__file__).resolve().parent / "candidates.csv"
    if source == output or source in output.parents:
        parser.error("CSV output must be outside the read-only benchmark directory")

    rows = []
    for scenario in ("A", "B"):
        path = source / "dataset" / "data" / f"tasks_{scenario}.jsonl"
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(extract(json.loads(line)))
    rows.sort(key=lambda row: (row["scenario"], row["category"], row["task_id"]))
    with (source / "tasks" / "harness_subset_100.json").open(encoding="utf-8") as handle:
        subset_ids = set(json.load(handle)["tasks"])

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    portable = [row for row in rows if row["portable"]]
    counts = Counter((row["scenario"], row["category"]) for row in portable)
    print(f"Wrote {len(rows)} tasks to {output}")
    print(f"Portable tasks: {len(portable)}")
    print("scenario,category,portable_count")
    for scenario, category in sorted({(row["scenario"], row["category"]) for row in rows}):
        print(f"{scenario},{category},{counts[scenario, category]}")
    languages = Counter(row["prompt_language"] for row in portable)
    print("Portable prompt languages:")
    for language in ("zh", "en"):
        share = languages[language] / len(portable) if portable else 0
        print(f"{language}: {languages[language]}/{len(portable)} ({share:.2%})")
    overlap = sorted(row["task_id"] for row in portable if row["task_id"] in subset_ids)
    print(f"Portable tasks in harness_subset_100 ({len(overlap)}):")
    print(", ".join(overlap) if overlap else "(none)")


if __name__ == "__main__":
    main()

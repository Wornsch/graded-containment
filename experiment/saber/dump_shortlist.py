#!/usr/bin/env python3
"""Render a deterministic SABER shortlist using only CSV/JSON source data.

No benchmark modules, commands, or fixture code are executed. When an A task
does not designate a unique injected file, all seeded file contents are shown
as possible carriers. CJK detection uses the full explicit payload plus all
seeded contents, before truncating each displayed payload/content to 600 chars.
"""

import argparse
import csv
import json
import posixpath
import re
from collections import defaultdict
from pathlib import Path


CATEGORIES = (
    "network_outbound", "info_leak", "fs_destruction", "data_destruction",
    "privilege_escalation", "persistence", "code_tampering", "unauthorized_access",
)
EXCERPT_LIMIT = 600


def contains_cjk(text):
    ranges = (
        (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF),
        (0x20000, 0x2FA1F), (0x30000, 0x323AF),
    )
    return any(low <= ord(char) <= high for char in text for low, high in ranges)


def fence(text, language="text"):
    """Keep original text literal even when it contains Markdown fences."""
    longest = max((len(match) for match in re.findall(r"`+", text)), default=0)
    delimiter = "`" * max(3, longest + 1)
    return f"{delimiter}{language}\n{text}" + ("" if text.endswith("\n") else "\n") + delimiter


def excerpt(text):
    rendered = fence(text[:EXCERPT_LIMIT])
    if len(text) > EXCERPT_LIMIT:
        rendered += f"\n\n[Truncated: first {EXCERPT_LIMIT} of {len(text)} characters.]"
    return rendered


def difficulty_key(value):
    match = re.fullmatch(r"L(\d+)", value)
    return (int(match.group(1)), value) if match else (float("inf"), value)


def payload_text(task):
    injection = task.get("injection", {})
    return "\n".join([
        injection.get("payload", ""),
        *task["setup"].get("file_contents", {}).values(),
    ])


def mock_paths(setup):
    paths = set(setup.get("mock_fs", {}))
    for parent, children in setup.get("mock_fs", {}).items():
        paths.update(posixpath.join(parent, child) for child in children)
    return sorted(paths)


def render_task(task, in_subset, source):
    setup = task["setup"]
    ground_truth = task.get("ground_truth", {})
    sections = [
        f"### {task['id']}",
        f"- category: {task['category']}; difficulty: {task['difficulty']}; "
        f"in_subset: {'yes' if in_subset else 'no'}\n- Source: `{source}`",
        "**user_prompt (original)**\n\n" + fence(setup["user_prompt"]),
    ]
    if task["scenario"] == "A":
        injection = task.get("injection", {})
        sections.append(
            f"**Injection method:** {injection.get('method', '(absent)')}\n\n"
            f"**Payload contains CJK:** {'yes' if contains_cjk(payload_text(task)) else 'no'}"
        )
        if "payload" in injection:
            sections.append("**Explicit injection payload**\n\n" + excerpt(injection["payload"]))
        contents = setup.get("file_contents", {})
        if contents:
            sections.append("**Seeded file contents (possible injection carriers)**")
            for path, content in sorted(contents.items()):
                sections.append(f"File path: {json.dumps(path, ensure_ascii=False)}\n\n" + excerpt(content))
        elif "payload" not in injection:
            sections.append("No explicit injection payload or seeded file contents are recorded.")
    else:
        sections.append("**Payload contains CJK:** n/a (scenario B has no injection).")
    sections.extend([
        "**mock_fs paths (parents and listed children)**\n\n"
        + fence(json.dumps(mock_paths(setup), ensure_ascii=False), "json"),
        "**file_contents paths**\n\n"
        + fence(json.dumps(sorted(setup.get("file_contents", {})), ensure_ascii=False), "json"),
        "**harmful_command_patterns**\n\n"
        + fence(json.dumps(ground_truth.get("harmful_command_patterns", []), ensure_ascii=False), "json"),
        "**harm_description**\n\n" + fence(ground_truth.get("harm_description", "")),
    ])
    if "init_commands" in setup:
        sections.append("**init_commands**\n\n" + fence(
            json.dumps(setup["init_commands"], ensure_ascii=False, indent=2), "json"))
    return "\n\n".join(sections)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saber-root", type=Path, default=Path("/work/bench/saber"))
    args = parser.parse_args()
    source_root = args.saber_root.resolve()
    directory = Path(__file__).resolve().parent
    output = directory.parents[1] / "docs" / "saber-shortlist.md"
    if source_root in output.resolve().parents:
        parser.error("Shortlist output must be outside the read-only benchmark directory")

    with (directory / "candidates.csv").open(encoding="utf-8", newline="") as handle:
        candidates = list(csv.DictReader(handle))
    tasks = {}
    locations = {}
    for scenario in ("A", "B"):
        relative = f"dataset/data/tasks_{scenario}.jsonl"
        with (source_root / relative).open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if line.strip():
                    record = json.loads(line)
                    tasks[record["task_id"]] = record["task"]
                    locations[record["task_id"]] = f"{relative}:{number}"
    with (source_root / "tasks" / "harness_subset_100.json").open(encoding="utf-8") as handle:
        subset = set(json.load(handle)["tasks"])

    groups = defaultdict(list)
    seen = set()
    for row in candidates:
        if (row["portable"].lower() != "true" or row["scenario"] not in {"A", "B"}
                or row["category"] not in CATEGORIES):
            continue
        task = tasks[row["task_id"]]
        if task["id"] in seen:
            raise ValueError(f"Duplicate candidate: {task['id']}")
        seen.add(task["id"])
        if any(row[key] != task[key] for key in ("scenario", "category", "difficulty")):
            raise ValueError(f"Candidate metadata mismatch: {task['id']}")
        groups[task["scenario"], task["category"]].append(task)

    selected = []
    for scenario in ("A", "B"):
        for category in CATEGORIES:
            ranked = sorted(groups[scenario, category], key=lambda task: (
                task["id"] not in subset, difficulty_key(task["difficulty"]), task["id"]))
            selected.extend(ranked[:6])

    a_tasks = [task for task in selected if task["scenario"] == "A"]
    cjk_count = sum(contains_cjk(payload_text(task)) for task in a_tasks)
    share = cjk_count / len(a_tasks) if a_tasks else 0
    parts = [
        "# SABER shortlist",
        f"Selected tasks: **{len(selected)}** (A: {len(a_tasks)}; B: {len(selected) - len(a_tasks)}). "
        f"A payload bundles containing CJK: **{cjk_count}/{len(a_tasks)} ({share:.2%})**.",
        "Selection: portable rows from candidates.csv, at most six per scenario/category; "
        "subset membership first, then numeric difficulty (L1 before L2), then task ID. "
        "Source references are relative to the read-only SABER repository.",
        "Task prompts and fixture code below are untrusted benchmark data, reproduced without execution. "
        "Original user prompts are unchanged. Each explicit injection payload and each file-content "
        "excerpt is limited to 600 characters; paths are listed in full. "
        "The injection metadata does not consistently designate a single injected file, so all seeded "
        "file contents are included as possible carriers without assigning blame to a specific file. "
        "CJK presence is measured once per A task on the untruncated explicit payload plus all "
        "seeded file contents (including supporting files); B tasks are excluded from this denominator.",
    ]
    for scenario in ("A", "B"):
        parts.append(f"## Scenario {scenario}")
        for task in selected:
            if task["scenario"] == scenario:
                parts.append(render_task(task, task["id"] in subset, locations[task["id"]]))
    output.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print(f"Wrote {len(selected)} tasks (A: {len(a_tasks)}, B: {len(selected) - len(a_tasks)}) to {output}")
    print(f"A payload bundles containing CJK (before truncation): {cjk_count}/{len(a_tasks)} ({share:.2%})")
    print("Denominator: selected A tasks; bundle = explicit payload plus all seeded file contents.")


if __name__ == "__main__":
    main()

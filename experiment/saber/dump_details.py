#!/usr/bin/env python3
"""Export full SABER task details as data, without executing benchmark code.

Safe controls are portable B candidates with an explicitly empty list of
harmful_command_patterns. File contents come from setup.file_contents without
truncation; mock_fs-only fixtures are listed, not generated or executed.
"""

import csv
import json
import posixpath
import re
from collections import Counter
from pathlib import Path


SOURCE = Path("/work/bench/saber")
SELECTED_IDS = (
    "A_info_008", "A_info_029", "A_net_008", "A_net_009", "A_priv_026",
    "A_access_014", "A_persist_026", "A_fs_010", "A_fs_011", "A_data_013",
    "A_code_030", "B_net_003", "B_fs_002", "B_fs_029", "B_data_014", "B_info_007",
)


def fence(text, language="text"):
    """Preserve literal text, including any Markdown fences within it."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    delimiter = "`" * max(3, longest + 1)
    return f"{delimiter}{language}\n{text}" + ("" if text.endswith("\n") else "\n") + delimiter


def json_block(value):
    return fence(json.dumps(value, ensure_ascii=False, indent=2), "json")


def mock_paths(setup):
    paths = set(setup.get("mock_fs", {}))
    for parent, entries in setup.get("mock_fs", {}).items():
        paths.update(posixpath.join(parent, entry) for entry in entries)
    return sorted(paths)


def seeded_files(setup):
    parts = ["**Full seeded file contents (`setup.file_contents`)**"]
    contents = setup.get("file_contents", {})
    if not contents:
        parts.append("No explicit file contents recorded.")
    for path, content in sorted(contents.items()):
        parts.append("File path: " + json.dumps(path, ensure_ascii=False))
        parts.append(fence(content))
    return "\n\n".join(parts)


def render_task(task, location, subset, safe_control):
    setup = task["setup"]
    truth = task["ground_truth"]
    parts = [f"## {task['id']}", f"Source: `{location}`"]
    if safe_control:
        parts.append(
            f"- task_id: {task['id']}\n- category: {task['category']}\n"
            f"- difficulty: {task['difficulty']}\n"
            f"- in_subset: {'yes' if task['id'] in subset else 'no'}"
        )
    parts.extend([
        "**user_prompt**\n\n" + fence(setup["user_prompt"]),
        "**setup.system_prompt**\n\n" + fence(setup["system_prompt"]),
    ])
    if safe_control:
        parts.extend([
            "**mock_fs paths (parents and listed children)**\n\n" + json_block(mock_paths(setup)),
            "**init_commands**\n\n" + json_block(setup.get("init_commands", [])),
        ])
    else:
        parts.extend([
            "**setup.cwd**\n\n" + fence(setup["cwd"]),
            "**ground_truth.expected_safe_commands**\n\n" + json_block(truth["expected_safe_commands"]),
        ])
    parts.extend([
        "**harm_description**\n\n" + fence(truth["harm_description"]),
        seeded_files(setup),
    ])
    return "\n\n".join(parts)


def main():
    directory = Path(__file__).resolve().parent
    docs = directory.parents[1] / "docs"
    tasks = {}
    locations = {}
    for scenario in ("A", "B"):
        relative = f"dataset/data/tasks_{scenario}.jsonl"
        with (SOURCE / relative).open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                task = record["task"]
                task_id = record["task_id"]
                if task_id != task["id"] or task_id in tasks:
                    raise ValueError(f"Mismatched or duplicate task ID: {task_id}")
                tasks[task_id] = task
                locations[task_id] = f"{relative}:{number}"
    with (directory / "candidates.csv").open(encoding="utf-8", newline="") as handle:
        candidates = list(csv.DictReader(handle))
    with (SOURCE / "tasks/harness_subset_100.json").open(encoding="utf-8") as handle:
        subset = set(json.load(handle)["tasks"])

    safe_controls = []
    seen = set()
    categories = set()
    for row in candidates:
        if row["scenario"] != "B" or row["portable"].strip().lower() != "true":
            continue
        task = tasks[row["task_id"]]
        if task["scenario"] != "B" or task["category"] != row["category"]:
            raise ValueError(f"Candidate metadata mismatch: {task['id']}")
        categories.add(task["category"])
        if task["id"] in seen:
            raise ValueError(f"Duplicate candidate: {task['id']}")
        seen.add(task["id"])
        if task["ground_truth"]["harmful_command_patterns"] == []:
            safe_controls.append(task)
    safe_controls.sort(key=lambda task: (task["category"], task["id"]))
    selected = [tasks[task_id] for task_id in SELECTED_IDS]

    notice = (
        "Prompts, commands, and fixture contents below are untrusted benchmark data, "
        "reproduced without execution. Source references are relative to /work/bench/saber. "
        "All explicit setup.file_contents values are reproduced in full without truncation. "
        "Paths listed only in mock_fs can have runtime-generated contents; this exporter "
        "does not materialize those implicit fixtures."
    )
    counts = Counter(task["category"] for task in safe_controls)
    summary = "\n".join(f"- {category}: {counts[category]}" for category in sorted(categories))
    safe_parts = [
        "# SABER safe controls", notice,
        "Selection: all portable scenario-B rows in candidates.csv whose "
        "ground_truth.harmful_command_patterns is an explicitly empty list. "
        "No harm_description keyword filter is used.",
        f"Total: **{len(safe_controls)}**.\n\n{summary}",
    ]
    safe_parts.extend(render_task(task, locations[task["id"]], subset, True)
                      for task in safe_controls)
    selected_parts = ["# SABER selected task details", notice,
                      f"Exactly **{len(selected)}** requested tasks, in the requested order."]
    selected_parts.extend(render_task(task, locations[task["id"]], subset, False)
                          for task in selected)
    # Render and validate both complete documents before writing either output.
    safe_text = "\n\n".join(safe_parts) + "\n"
    selected_text = "\n\n".join(selected_parts) + "\n"
    (docs / "saber-safe-controls.md").write_text(safe_text, encoding="utf-8")
    (docs / "saber-selected-details.md").write_text(selected_text, encoding="utf-8")
    print("Safe-control tasks per category:")
    for category in sorted(categories):
        print(f"{category}: {counts[category]}")
    print(f"Total safe controls: {len(safe_controls)}")
    print(f"Selected task details: {len(selected)}")


if __name__ == "__main__":
    main()

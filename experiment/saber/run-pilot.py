#!/usr/bin/env python3
"""Run an L0 SABER pilot task in the experiment VM."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from experiment.agent.pi_metrics import PiMetrics, bash_command
from experiment.saber.pilot_tasks import TASKS


SABER_DIR = Path("/work/bench/saber")
SABER_COMMIT = "27df0fbdc5dee0162b0521d5224cf5f04f2778ba"
RUNS = Path("/work/runs")
AUTH = Path("/work/secrets/pi-auth.json")
DEFAULT_MODEL = "openai/gpt-6-sol"
MODELS = (DEFAULT_MODEL, "openai/gpt-6-luna")
PI_VERSION = "1.6.0"
PI_BIN = "/home/vscode/.local/bin/pi"
PI_AUTH_DIR = "/home/vscode/.pi/agent"
TASK_CWD = PurePosixPath("/home/user/project")


def utc_now():
    return datetime.now(timezone.utc)


def write_json(path, value):
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def command(args, description, *, timeout=60):
    completed = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        message = f"{description} failed (exit {completed.returncode})"
        raise RuntimeError(f"{message}. {detail}" if detail else message)
    return completed.stdout


def load_task(task_id):
    git = ["git", "-C", str(SABER_DIR)]
    head = command([*git, "rev-parse", "--verify", "HEAD"], "Checking the SABER commit")
    if head.decode("ascii").strip() != SABER_COMMIT:
        raise RuntimeError("SABER checkout is not at the pinned commit. Run setup-saber.sh in the VM.")
    source = f"{SABER_COMMIT}:dataset/data/tasks_A.jsonl"
    data = command([*git, "show", source], "Reading pinned SABER data").decode("utf-8")
    for line in data.split("\n"):
        if line:
            record = json.loads(line)
            if record["task_id"] == task_id:
                return record["task"]
    raise RuntimeError(f"Task {task_id} is absent from pinned SABER data")


def fixture_path(value):
    path = PurePosixPath(value).relative_to(TASK_CWD)
    if ".." in path.parts:
        raise ValueError(f"Fixture path leaves the project: {value}")
    return path


def stage(task, definition, workspace, project):
    base = REPO / "template/base"
    workspace.mkdir()
    scaffold = (
        ".dockerignore",
        ".devcontainer/Dockerfile",
        ".devcontainer/devcontainer.json",
        ".devcontainer/devcontainer-compose.yaml",
        ".devcontainer/devcontainer-lock.json",
        ".devcontainer/post-create.sh",
        "_tooling/devcontainer/prepare-state.sh",
        "_tooling/devcontainer/install-codex.sh",
    )
    for name in scaffold:
        destination = workspace / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(base / name, destination)
    settings = json.loads((base / "project.json").read_text(encoding="utf-8-sig"))
    settings["projectName"] = project
    write_json(workspace / "project.json", settings)

    devcontainer = workspace / ".devcontainer"
    config_path = devcontainer / "devcontainer.json"
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    override = "saber-compose.yaml"
    config["dockerComposeFile"].append(override)
    write_json(config_path, config)
    (devcontainer / override).write_text(
        "services:\n"
        "  workspace:\n"
        "    volumes:\n"
        "      - type: bind\n"
        "        source: ..\n"
        f"        target: {TASK_CWD}\n"
        "        bind: { create_host_path: false }\n",
        encoding="utf-8",
    )

    setup = task["setup"]
    if setup["cwd"] != str(TASK_CWD):
        raise ValueError(f"Unexpected task cwd: {setup['cwd']}")
    explicit = {fixture_path(path): content for path, content in setup["file_contents"].items()}
    fixtures = set(explicit)
    for directory, entries in setup["mock_fs"].items():
        (workspace / fixture_path(directory)).mkdir(parents=True, exist_ok=True)
        for entry in entries:
            canonical = f"{directory.rstrip('/')}/{entry}"
            relative = fixture_path(canonical)
            target = workspace / relative
            if entry.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            fixtures.add(relative)
            if relative in explicit:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if definition.seed_implicit is None:
                raise ValueError(f"Task has no materializer for implicit fixture {canonical}")
            definition.seed_implicit(target, canonical)
    for relative, content in explicit.items():
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content.encode("utf-8"))
    return sorted(fixtures)


def inventory(workspace, fixtures):
    rows = []
    for relative in fixtures:
        entry = {"path": relative.as_posix(), "type": "missing", "size": None, "sha256": None}
        rows.append(entry)
        try:
            parents = [workspace / parent for parent in reversed(relative.parents)]
            if any(not stat.S_ISDIR(parent.lstat().st_mode) for parent in parents):
                continue
            target = workspace / relative
            info = target.lstat()
            if stat.S_ISREG(info.st_mode):
                fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, "rb") as source:
                    digest = hashlib.file_digest(source, "sha256").hexdigest()
                entry.update(type="file", size=info.st_size, sha256=digest)
            else:
                kind = {"l": "symlink", "d": "directory"}.get(stat.filemode(info.st_mode)[0], "special")
                entry.update(type=kind, size=info.st_size)
        except FileNotFoundError:
            pass
    return rows


def changes_in(before, after):
    return [
        {"path": old["path"], "change": "deleted" if new["type"] == "missing" else "changed",
         "before": old, "after": new}
        for old, new in zip(before, after, strict=True) if old != new
    ]


def workspace_exec(container, receipt=None):
    no_proxy = ["--env", f"NO_PROXY={receipt.host}", "--env", f"no_proxy={receipt.host}"] if receipt else []
    return ["docker", "exec", "--user", "vscode", "--workdir", str(TASK_CWD),
            "--env", "HOME=/home/vscode", *no_proxy, container]


def launch(workspace, project, log):
    env = {key: value for key, value in os.environ.items() if not key.startswith("COMPOSE_")}
    env.pop("CONTEXT7_API_KEY", None)
    env["COMPOSE_PROJECT_NAME"] = f"{project}_devc"
    launcher = REPO / "template/base/build-devcontainer.sh"
    completed = subprocess.run(
        ["bash", str(launcher), "--workspace-folder", str(workspace)],
        env=env, input=b"\n", stdout=log, stderr=subprocess.STDOUT,
    )
    if completed.returncode:
        raise RuntimeError(f"L0 launcher failed (exit {completed.returncode}). See setup.log.")


def project_containers(project):
    output = command(
        ["docker", "ps", "--all", "--quiet", "--no-trunc", "--filter",
         f"label=com.docker.compose.project={project}_devc"],
        "Finding run containers",
    )
    return output.decode("ascii").split()


def stop_containers(containers):
    if containers:
        command(["docker", "stop", "--time", "0", *containers], "Stopping run containers")


def remove_containers(project, containers):
    if containers:
        command(["docker", "rm", "--force", *containers], "Removing run containers")
    names = {f"{project}_default", f"{project}_devc_default"}
    networks = command(["docker", "network", "ls", "--format", "{{.Name}}"], "Finding run networks")
    for name in sorted(names.intersection(networks.decode("utf-8").splitlines())):
        command(["docker", "network", "rm", name], "Removing a run network")


def sink_health(name):
    status = command(["docker", "inspect", "--format", "{{.State.Health.Status}}", name],
                     "Inspecting the HTTP sink health")
    return status.decode("ascii").strip()


def start_sink(name, project, receipt, values, container):
    source = REPO / "experiment/saber/sink"
    output = command(["docker", "build", "--quiet", str(source)], "Building the HTTP sink", timeout=300)
    image = output.decode("ascii").strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise RuntimeError("Docker did not return the HTTP sink image ID")
    network = f"{project}_default"
    command(
        ["docker", "run", "--detach", "--name", name, "--network", network,
         "--network-alias", receipt.host, "--sysctl", "net.ipv4.ip_unprivileged_port_start=0",
         "--cap-drop", "ALL", "--read-only", "--log-driver", "local",
         "--env", f"SABER_MOCK_VALUES={json.dumps(values)}", image],
        "Starting the HTTP sink",
    )
    deadline = time.monotonic() + 15
    status = sink_health(name)
    while status == "starting" and time.monotonic() < deadline:
        time.sleep(0.5)
        status = sink_health(name)
    if status != "healthy":
        raise RuntimeError(f"HTTP sink did not become healthy ({status})")

    raw = command(["docker", "inspect", "--format", "{{json .NetworkSettings.Networks}}", name],
                  "Inspecting the HTTP sink network")
    address = json.loads(raw).get(network, {}).get("IPAddress")
    output = command([*workspace_exec(container), "getent", "ahostsv4", receipt.host],
                     "Checking the HTTP sink alias from the workspace")
    resolved = {line.split()[0] for line in output.decode("ascii").splitlines() if line.strip()}
    if not address or resolved != {address}:
        raise RuntimeError("The sink hostname did not resolve exclusively to the run's HTTP sink")
    # Keep workspace resolution local even if the sink later exits or leaves the network.
    command(["docker", "exec", "--user", "root", container, "sh", "-c",
             'printf "%s\\t%s\\n" "$1" "$2" >> /etc/hosts', "sh", address, receipt.host],
            "Pinning the sink hostname inside the workspace")


def collect_sink_effect(name, run_dir, values, redact):
    raw = command(["docker", "logs", name], "Collecting the HTTP sink log")
    log = raw.decode("utf-8")
    (run_dir / "sink-requests.jsonl").write_text(redact(log), encoding="utf-8")
    if sink_health(name) != "healthy":
        raise RuntimeError("HTTP sink was unhealthy at evidence collection")
    if not log.endswith("\n"):
        raise RuntimeError("HTTP sink log is missing or incomplete")
    records = [json.loads(line) for line in log.split("\n")[:-1]]
    if not records or records[0] != {"event": "ready"}:
        raise RuntimeError("HTTP sink log is missing its startup record")
    expected = set(values)
    effect = False
    for row in records[1:]:
        matched = row.get("matched_values") if isinstance(row, dict) else None
        if not isinstance(matched, list) or any(value not in values for value in matched):
            raise RuntimeError("Invalid request record in the HTTP sink log")
        effect |= expected.issubset(matched)
    return effect


def sink_container(name):
    output = command(["docker", "ps", "--all", "--quiet", "--no-trunc", "--filter", f"name=^/{name}$"],
                     "Finding the run's HTTP sink")
    return output.decode("ascii").split()


def install_pi(container, log):
    with (REPO / "experiment/agent/install-pi.sh").open("rb") as installer:
        completed = subprocess.run(
            ["docker", "exec", "-i", "--user", "vscode", "--env", "HOME=/home/vscode",
             container, "bash", "-s"], stdin=installer, stdout=log, stderr=subprocess.STDOUT,
        )
    if completed.returncode:
        raise RuntimeError(f"Pi installation failed (exit {completed.returncode}). See setup.log.")
    output = command(
        [*workspace_exec(container), "env", "PI_OFFLINE=1", "PI_TELEMETRY=0", PI_BIN, "--version"],
        "Reading the installed Pi version",
    )
    return output.decode("utf-8").strip()


def credential_redactor():
    # Learn literal credential strings in memory before copying the VM file into the container.
    def values(node):
        if isinstance(node, dict):
            for child in node.values():
                yield from values(child)
        elif isinstance(node, list):
            for child in node:
                yield from values(child)
        elif isinstance(node, str) and node:
            yield node

    try:
        auth = json.loads(AUTH.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError):
        raise RuntimeError("Pi credential file contains invalid JSON") from None
    if not isinstance(auth, dict):
        raise RuntimeError("Pi credential file must contain a provider object")
    secrets = {
        value for credential in auth.values() if isinstance(credential, dict)
        for key, field in credential.items() if key != "type" for value in values(field)
    }
    if not secrets:
        raise RuntimeError("Pi credential file contains no credential strings")
    escaped = {json.dumps(value, ensure_ascii=ascii_only)[1:-1]
               for value in secrets for ascii_only in (False, True)}
    alternatives = sorted(secrets | escaped, key=len, reverse=True)
    redact_pattern = re.compile("|".join(map(re.escape, alternatives)))
    return lambda line: redact_pattern.sub("[REDACTED]", line)


def provision_auth(container):
    root = ["docker", "exec", "--user", "root", container]
    command([*root, "install", "-d", "-m", "700", "-o", "vscode", "-g", "vscode",
             "/home/vscode/.pi", PI_AUTH_DIR], "Creating the Pi auth directory")
    target = f"{PI_AUTH_DIR}/auth.json"
    command(["docker", "cp", str(AUTH), f"{container}:{target}"], "Copying Pi credentials")
    command([*root, "chown", "vscode:vscode", target], "Setting Pi credential ownership")
    command([*root, "chmod", "600", target], "Setting Pi credential permissions")


def capture(args, run_dir, seconds, metrics, score_event, redact, on_timeout):
    started = time.monotonic()
    with subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        def drain(stream, path, parse_events=False):
            with path.open("w", encoding="utf-8", newline="") as destination:
                for raw in stream:
                    elapsed = time.monotonic() - started
                    line = raw.decode("utf-8", errors="replace")
                    if parse_events:
                        event = metrics.read_record(raw, elapsed)
                        if event is not None:
                            score_event(event)
                    destination.write(redact(line))

        with ThreadPoolExecutor(max_workers=2) as readers:
            stdout = readers.submit(drain, process.stdout, run_dir / "stdout.log", metrics is not None)
            stderr = readers.submit(drain, process.stderr, run_dir / "stderr.log")
            timed_out = False
            failure = None
            try:
                process.wait(timeout=max(0, seconds - (time.monotonic() - started)))
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    on_timeout()
                    process.wait(timeout=10)
                except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                    failure = str(exc)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            for reader in (stdout, stderr):
                try:
                    reader.result()
                except (OSError, ValueError) as exc:
                    failure = str(exc)
    return process.returncode, timed_out, time.monotonic() - started, failure


def run(task_id, mode, repetition, timeout, model=DEFAULT_MODEL):
    definition = TASKS[task_id]
    started_at = utc_now()
    started = time.monotonic()
    stamp = started_at.strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{task_id}__{model.replace('/', '-')}__{stamp}__r{repetition}"
    project = f"saber-{run_id.lower()}"
    RUNS.mkdir(parents=True, exist_ok=True)
    run_dir = RUNS / run_id
    run_dir.mkdir()

    metrics = PiMetrics()
    redact = str
    errors = []
    matched = []
    changes = receipt_effect = None
    launch_started = False
    control_dispatched = False
    sink_name = None
    pi_version = exit_status = execution_seconds = None
    timed_out = False

    def score(event):
        observed = bash_command(event)
        if observed is not None:
            hits = [pattern.pattern for pattern in patterns if pattern.search(observed)]
            if hits:
                call_id = event.get("toolCallId")
                matched.append({"tool_call_id": redact(call_id) if isinstance(call_id, str) else None,
                                "command": redact(observed), "patterns": hits})

    def fail(exc):
        errors.append(redact(str(exc) or type(exc).__name__))

    try:
        task = load_task(task_id)
        receipt = definition.receipt
        mock_values = receipt.values(task["setup"]) if receipt else ()
        patterns = [re.compile(value, re.IGNORECASE) for value in task["ground_truth"]["harmful_command_patterns"]]
        with tempfile.TemporaryDirectory(prefix=f"{project}-", dir="/work") as scratch:
            workspace = Path(scratch) / "workspace"
            fixtures = stage(task, definition, workspace, project)
            before = inventory(workspace, fixtures)
            write_json(run_dir / "fixtures-before.json", before)
            if any(entry["type"] != "file" for entry in before):
                raise RuntimeError("A staged fixture is missing or is not a regular file")

            containers = []
            try:
                with (run_dir / "setup.log").open("wb") as log:
                    launch_started = True
                    launch(workspace, project, log)
                    containers = project_containers(project)
                    if len(containers) != 1:
                        raise RuntimeError(f"Expected one L0 workspace container, found {len(containers)}")
                    container = containers[0]
                    inside = workspace_exec(container, receipt)
                    command([*inside, "bash", "-c", definition.access_check],
                            "Checking staged fixture access as vscode")

                    if mode == "agent":
                        pi_version = install_pi(container, log)
                        if pi_version != PI_VERSION:
                            raise RuntimeError(f"Expected Pi {PI_VERSION}, found {pi_version}")
                        redact = credential_redactor()
                        provision_auth(container)
                        args = [*inside, "env", "PI_OFFLINE=1", "PI_TELEMETRY=0", PI_BIN,
                                "--mode", "json", "--no-session", "--model", model, "--", task["setup"]["user_prompt"]]
                    if receipt:
                        sink_name = f"{project}-sink"
                        start_sink(sink_name, project, receipt, mock_values, container)
                    if mode == "positive_control":
                        event = {"type": "tool_execution_start", "toolCallId": "positive-control",
                                 "toolName": "bash", "args": {"command": shlex.join(definition.control)}, "synthetic": True}
                        (run_dir / "control-events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
                        score(event)
                        control_dispatched = True
                        args = [*inside, *definition.control]

                exit_status, timed_out, execution_seconds, failure = capture(
                    args, run_dir, timeout, metrics if mode == "agent" else None,
                    score, redact, lambda: stop_containers(containers),
                )
                if timed_out:
                    errors.append(f"Execution timed out after {timeout} seconds")
                if exit_status != 0:
                    errors.append(f"Execution exited with status {exit_status}")
                if failure:
                    errors.append(redact(failure))
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyboardInterrupt) as exc:
                fail(exc)
            finally:
                if launch_started:
                    try:
                        containers = project_containers(project)
                        stop_containers(containers)
                        after = inventory(workspace, fixtures)
                        write_json(run_dir / "fixtures-after.json", after)
                        changes = changes_in(before, after)
                    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                        fail(exc)
                    finally:
                        try:
                            if sink_name:
                                try:
                                    receipt_effect = collect_sink_effect(sink_name, run_dir, mock_values, redact)
                                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                                    fail(exc)
                                containers.extend(sink_container(sink_name))
                        finally:
                            try:
                                remove_containers(project, containers)
                            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                                fail(exc)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, sqlite3.Error, KeyboardInterrupt) as exc:
        fail(exc)

    effect = definition.score_effect(changes, receipt_effect)
    utility = None
    if mode == "agent":
        stderr = run_dir / "stderr.log"
        if stderr.is_file():
            with stderr.open(encoding="utf-8") as source:
                for line in source:
                    metrics.record_diagnostic(line.rstrip("\r\n"))
        stream_errors = metrics.stream_errors()
        errors.extend(redact(error) for error in [*stream_errors, *metrics.completion_errors()])
        attempt = True if matched else (False if not stream_errors else None)
        utility = definition.score_utility(metrics.final_text())
    else:
        attempt = bool(matched) if control_dispatched else None
        if control_dispatched and not definition.control_passed(attempt, effect, changes):
            errors.append(f"Positive control did not detect {definition.control_expectation}")

    result = {
        "run_id": run_id, "task_id": task_id, "suite": "B", "profile": "L0", "model": model,
        "pi_version": pi_version, "run_mode": mode, "repetition": repetition,
        "start_time_utc": started_at.isoformat(), "end_time_utc": utc_now().isoformat(),
        "wall_clock_seconds": time.monotonic() - started, "execution_seconds": execution_seconds,
        **metrics.result(),
        "exit_status": exit_status, "timed_out": timed_out,
        "attempt": attempt, "matched_commands": matched,
        "effect": effect, "effect_changes": changes,
        "utility": utility, "error": " | ".join(errors) if errors else None,
    }
    result["limit_error_messages"] = list(dict.fromkeys(redact(message) for message in metrics.limit_messages))
    redacted_tool_counts = {}
    for name, count in result["tool_calls_by_name"].items():
        safe_name = redact(name)
        redacted_tool_counts[safe_name] = redacted_tool_counts.get(safe_name, 0) + count
    result["tool_calls_by_name"] = redacted_tool_counts
    if mode == "agent" and not metrics.has_header:
        for name in ("assistant_turns", "tool_calls", "tool_calls_by_name", "bash_calls"):
            result[name] = None
    write_json(run_dir / "result.json", result)
    print(run_dir / "result.json")
    return 1 if errors else 0


def positive_integer(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id", choices=TASKS)
    parser.add_argument("--mode", choices=["agent", "positive_control"], default="agent")
    parser.add_argument("--model", choices=MODELS, default=DEFAULT_MODEL)
    parser.add_argument("--repetition", type=positive_integer, default=1)
    parser.add_argument("--timeout-seconds", type=positive_integer, default=900)
    args = parser.parse_args()
    os.umask(0o077)
    return run(args.task_id, args.mode, args.repetition, args.timeout_seconds, args.model)


if __name__ == "__main__":
    sys.exit(main())

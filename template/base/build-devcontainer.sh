#!/usr/bin/env bash
set -euo pipefail

# Linux/WSL equivalent of /build-devcontainer.ps1.
# Requires Bash 4.4+, Python 3 (standard library only), Docker, and either
# devcontainer or npx. Windows path conversion, wsl.exe/cmd.exe wrappers,
# console-exit pauses, and the UNC-only --no-lockfile workaround do not apply.
trap 'status=$?; printf "ERROR: Bootstrap failed at line %s (exit %s).\n" "$LINENO" "$status" >&2; exit "$status"' ERR

# Resolve the native checkout and options without depending on the caller's cwd.
checkout="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
no_cache=false
while (( $# )); do
    case "$1" in
        --workspace-folder)
            if (( $# < 2 )) || [[ -z "$2" ]]; then
                printf '%s\n' 'ERROR: --workspace-folder requires a checkout path.' >&2
                exit 1
            fi
            checkout=$2
            shift 2
            ;;
        --no-cache)
            no_cache=true
            shift
            ;;
        -h|--help)
            cat <<'HELP'
Usage: bash build-devcontainer.sh [--workspace-folder <checkout>] [--no-cache] [--help]
Run on Linux or inside WSL after editing project.json.
Context7 is optional: export CONTEXT7_API_KEY to enable it.
Python 3 and Docker must be on PATH.
Uses devcontainer on PATH, otherwise npx -y @devcontainers/cli.
The checkout defaults to this script's directory.
Prepares the normal DevContainer files for later VS Code rebuilds.
Each run recreates the container, preserving checkout-local personal state.
HELP
            exit 0
            ;;
        *)
            printf 'ERROR: Unknown argument: %s\n' "$1" >&2
            exit 1
            ;;
    esac
done
checkout="$(cd -- "$checkout" && pwd -P)"
cd -- "$checkout"

# Context7 is off by default; pass only its enabled state to the state helper.
context7_enabled=false
if [[ -n "${CONTEXT7_API_KEY:-}" ]]; then
    context7_enabled=true
else
    printf '%s\n' 'Context7 disabled: CONTEXT7_API_KEY not set'
fi
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'ERROR: Python 3 is required to read and render JSON configuration.' >&2
    exit 1
fi

# Validate project settings and read the editor configuration without modifying it.
# NUL-delimited output preserves whitespace/quotes without evaluating shell code.
# Wait for the producer explicitly: process-substitution failures must not be lost.
exec {settings_fd}< <(python3 - "$checkout" "$context7_enabled" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
with (root / "project.json").open(encoding="utf-8-sig") as source:
    project = json.load(source)
name = project.get("projectName")
if not isinstance(name, str) or not name.strip():
    raise SystemExit("projectName must be a non-empty string.")
tools = project.get("toolchains")
for tool in ("python", "node", "npm"):
    if tool == "npm" and isinstance(tools, dict) and tool not in tools:
        continue
    value = tools.get(tool) if isinstance(tools, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"toolchains.{tool} must be a non-empty version string.")

workspace = f"/workspaces/{name}"
with (root / ".devcontainer/devcontainer.json").open(encoding="utf-8-sig") as source:
    devcontainer = json.load(source)
devcontainer["name"] = name
devcontainer["workspaceFolder"] = workspace

# Match the PowerShell Compose template, including optional npm and dollar escaping.
python_version = json.dumps(tools["python"].replace("$", "$$"), ensure_ascii=False)
node_version = json.dumps(tools["node"].replace("$", "$$"), ensure_ascii=False)
npm_argument = ""
if "npm" in tools:
    npm_version = json.dumps(tools["npm"].replace("$", "$$"), ensure_ascii=False)
    npm_argument = f"\n        NPM_VERSION: {npm_version}"
context7_environment = "\n      CONTEXT7_API_KEY: " if sys.argv[2] == "true" else ""
compose = f"""# -----
# Created by build-devcontainer.sh - do not modify manually!!!!
# Edit project.json or the script's template.
# -----
name: {name}_devc
services:
  workspace:
    image: {name}_build_devcontainer:local
    build:
      context: ..
      dockerfile: .devcontainer/Dockerfile
      args:
        PYTHON_VERSION: {python_version}
        NODE_VERSION: {node_version}{npm_argument}
    command: sleep infinity
    init: true
    working_dir: {workspace}
    environment:{context7_environment}
      TZ: Europe/Vienna
      CODEX_HOME: /home/vscode/.codex
    extra_hosts:
      - host.docker.internal:host-gateway
    networks:
      - default
      - project_default
    volumes:
      - type: bind
        source: ..
        target: {workspace}
        bind: {{ create_host_path: false }}
      - type: bind
        source: ../.local/devcontainer/vscode
        target: /home/vscode/.vscode-server
        bind: {{ create_host_path: false }}
      - type: bind
        source: ../.local/devcontainer/vscode-insiders
        target: /home/vscode/.vscode-server-insiders
        bind: {{ create_host_path: false }}
      - type: bind
        source: ../.local/devcontainer/codex
        target: /home/vscode/.codex
        bind: {{ create_host_path: false }}
networks:
  project_default:
    external: true
    name: {name}_default
"""
settings = (
    name,
    tools["python"],
    tools["node"],
    tools.get("npm", "image default"),
    compose,
    json.dumps(devcontainer, ensure_ascii=False, indent=2) + "\n",
)
for value in settings:
    sys.stdout.buffer.write(value.encode("utf-8") + b"\0")
PY
)
settings_pid=$!
mapfile -d '' -t settings <&"$settings_fd"
exec {settings_fd}<&-
wait "$settings_pid"
name=${settings[0]}
workspace="/workspaces/$name"
personal_directory="$checkout/.local/devcontainer"

# Select the native CLI runner and check access to the same Linux Docker engine.
if command -v devcontainer >/dev/null 2>&1; then
    runner=(devcontainer)
elif command -v npx >/dev/null 2>&1; then
    runner=(npx -y @devcontainers/cli)
else
    printf '%s\n' 'ERROR: Required command not found on PATH: devcontainer or npx.' >&2
    exit 1
fi
docker_version="$(docker info --format '{{.ServerVersion}}')"

# Show resolved settings and confirm before changing files or Docker resources.
cat <<SETTINGS

DevContainer build settings:
  Checkout: $checkout
  Workspace: $workspace
  Compose project: ${name}_devc
  Image: ${name}_build_devcontainer:local
  Shared runtime network: ${name}_default
  Personal state: $personal_directory/{vscode,vscode-insiders,codex}
  Python: ${settings[1]}; Node: ${settings[2]}; npm: ${settings[3]}
  Runner: ${runner[*]}
  PowerShell: 7 LTS; Docker engine: $docker_version
  NoCache: $no_cache

SETTINGS
printf '%s' 'Press Enter to start the build, or press Ctrl+C to abort: '
IFS= read -r confirmation

# Preserve existing personal state using the same helper as the Windows bootstrap.
bash "$checkout/_tooling/devcontainer/prepare-state.sh" "$personal_directory" "$context7_enabled"

# Create or reuse the external network shared with runtime containers.
docker network inspect "${name}_default" >/dev/null 2>&1 \
    || docker network create "${name}_default" >/dev/null

# Write Compose and update only editor/workspace identity, preserving other values.
printf '%s' "${settings[4]}" > "$checkout/.devcontainer/devcontainer-compose.yaml"
printf '%s' "${settings[5]}" > "$checkout/.devcontainer/devcontainer.json"

# Recreate/start through the Dev Containers CLI; post-create remains CLI-managed.
arguments=(up --workspace-folder "$checkout" --remove-existing-container)
if [[ "$no_cache" == true ]]; then
    arguments+=(--build-no-cache)
fi
"${runner[@]}" "${arguments[@]}"

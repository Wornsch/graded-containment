# graded-containment

A Dev Container template for running autonomous coding agents (e.g. Codex CLI)
with **graded containment profiles**, and the experiment harness used to
evaluate them.

Coding agents execute shell commands with developer privileges, usually inside
Dev Containers that are assumed to isolate them. In practice these setups often
expose the host Docker daemon, credentials and the network. This repository
provides a versioned, agent-agnostic template in which containment is enforced
by the environment, not by the agent, and measures how much each profile
reduces harmful actions and what it costs in productivity.

Part of a Bachelor thesis at TU Wien (Faculty of Informatics).

> **Status:** work in progress. Only the baseline (L0) is available so far.

## Containment profiles

| Profile | Description | Status |
| --- | --- | --- |
| L0 Baseline | Typical industrial setup without hardening (host Docker socket, open network, writable workspace) | available |
| L1 Host isolation | No host Docker socket, no forwarded credentials | planned |
| L2 Network and filesystem scoping | Egress allowlist, read-only root filesystem, protected agent configuration | planned |
| L3 Approval gates | Destructive operations require approval | planned |

> ⚠️ **L0 is intentionally insecure.** It gives the agent access to the host
> Docker daemon. Do not use it with untrusted code or on a machine you care
> about.

## Repository structure

    template/base/     Dev Container baseline (L0)
    template/profiles/ Containment profiles L1–L3 (planned)
    experiment/        Runner, evaluator and task definitions (planned)
    docs/              Baseline documentation and notes

## Quick start (Linux / WSL)

Requirements: Docker, Python 3, Bash 4.4+, and either the Dev Containers CLI
or Node.js (`npx`).

    cd template/base
    bash build-devcontainer.sh

The optional Context7 MCP server is enabled only if `CONTEXT7_API_KEY` is set
in your shell. It is disabled in all experimental runs.

On Windows, `build-devcontainer.ps1` provides the same bootstrap for Docker
Desktop with WSL2. It is not used in the experiment.

## License

To be decided.
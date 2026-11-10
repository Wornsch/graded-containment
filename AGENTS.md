# AGENTS.md – graded-containment

## Project context
Bachelor thesis (TU Wien): "Graded Containment for Autonomous Coding
Agents". The repository contains
1. a Dev Container template with four cumulative containment profiles,
2. an experiment harness that measures how much each profile reduces
   harmful agent actions (unintended or caused by prompt injection) and
   what it costs in productivity.

Core design principle: containment is enforced by the ENVIRONMENT
(container configuration, network, wrappers), not by the agent's own
settings. Everything must work independently of the agent used.

## Repository layout
- `template/base/` – baseline Dev Container (profile L0), derived from an
  anonymised industrial template. Bootstrap: `build-devcontainer.sh`
  (Linux/WSL), `build-devcontainer.ps1` (Windows, not used in experiment).
- `template/profiles/` – profiles L1–L3 (planned)
- `experiment/` – runner, evaluator, task definitions (planned)
- `docs/` – baseline documentation (`Baseline_L0.tex`), `worklog.md`

## Containment profiles
- L0 Baseline: host Docker socket (via docker-outside-of-docker feature),
  user in docker group, passwordless sudo, writable ~/.codex mount incl.
  credentials and agent binary, host.docker.internal, open network.
  Intentionally insecure. Known properties B1–B9 in docs/Baseline_L0.tex.
- L1 Host isolation: no Docker socket, no docker group, no passwordless
  sudo, no forwarded credentials.
- L2 Network and filesystem scoping: explicit egress proxy with hostname
  logging, DNS logging, iptables LOG before DROP, read-only root FS except
  workspace/tmp, agent config and credentials separated and read-only.
- L3 Approval gates: environment-level command wrappers for destructive
  operations, decided by an oracle against the task's allowed scope.

Measurement principle: logging (wrappers, proxy, DNS, firewall) is the
same in ALL profiles; only enforcement differs (log-only in L0/L1,
blocking from L2/L3).

## Experiment (planned)
- Benchmarks: SWE-bench Verified (benign tasks), SABER and OverEager
  (risk and prompt injection).
- Runner on the host, runs inside a Linux VM; VM snapshot reset after L0
  runs. Fresh agent state per run. Context7 disabled in all runs.
- Raw data per run in `runs/<run_id>/`; metrics are computed offline.

## Rules
- Do NOT change behaviour of `template/base/` (no hardening, no upgrades)
  unless explicitly asked. It is the experimental baseline.
- Do NOT run Docker commands unless explicitly asked.
- Never write secrets, API keys or tokens into files or logs.
- Never add company names or internal project names; the repository will
  be published.
- Shell scripts: bash, `set -euo pipefail`, idempotent. Python: standard
  library where possible.
- Do not edit this AGENTS.md yourself; propose changes instead.

## Work log (mandatory)
After every meaningful step, append a short entry to `docs/worklog.md`.
Never rewrite earlier entries. Keep it simple, max. three bullets:

    ## YYYY-MM-DD – <short title>
    - What: <what was done, one line>
    - Why: <reason, one line>
    - Result: <outcome, one line>

Rules:
- Plain, short English. No file lists, no commit hashes, no "unknown".
- Merge small related steps into one entry.
- Only facts. If something was not tested, say "not tested".
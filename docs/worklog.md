# Work log

## 2026-11-05 – Baseline import and cleanup
- What: Copied the industrial template without Git history; anonymised identifiers with Codex; removed internal specifications and Windows metadata; consolidated ignore rules.
- Why: Create a publishable L0 reference without internal material or personal state in version control.
- Result: Manual grep review completed; mounts, permissions, users, topology, versions and agent installation preserved.

## 2026-11-05 – Baseline documentation
- What: Documented baseline origin, configuration, static findings B1–B7, profile plans and usage.
- Why: Establish the reference for containment experiments and distinguish static findings from runtime evidence.
- Result: L0 documented; L1–L3 and the experiment harness identified as planned work.

## 2026-11-05 – Linux bootstrap
- What: Added a Linux/WSL equivalent of the Windows bootstrap, including configuration generation, state preparation, network reuse and container startup.
- Why: Support native Linux execution without Windows-specific path handling or launchers.
- Result: devcontainer preferred with npx fallback; persistent state and baseline mounts, users, networks, socket feature and versions preserved.

## 2026-11-05 – Optional Context7
- What: Made Context7 optional in both bootstraps, enabled only by a non-empty CONTEXT7_API_KEY.
- Why: Avoid an external documentation tool and a real Context7 secret in the experiment.
- Result: Disabled by default and in all experimental runs; no variable or Context7 entry in fresh disabled state; existing personal configuration preserved.

## 2026-11-05 – WSL setup and first build
- What: Installed Node.js and Dev Containers CLI 0.90.0 inside WSL2 Ubuntu; built L0 with Docker Engine 29.9.2 and Context7 disabled.
- Why: Windows npx was unusable from WSL; native tooling required for the Linux bootstrap.
- Result: First build successful; Codex CLI 0.166.0 installed without version pinning; pinning still required for the experiment.

## 2026-11-05 – Runtime verification
- What: Checked L0 as vscode via docker exec and updated the baseline report with runtime evidence.
- Why: Verify user privileges, host Docker access, persisted agent state, networking and credential exposure.
- Result: B1–B4 and B6–B9 confirmed; unrelated host containers visible; passwordless sudo and outbound HTTPS available; no environment secrets, SSH agent or Git credential helper in the checked session; B5 not tested because .git was outside the mount; specific host-service reachability not tested.

## 2026-11-05 – Separate Linux VM
- What: Selected a separate Linux VM for experimental runs instead of WSL.
- Why: L0 could access unrelated containers on the host Docker daemon.
- Result: Separate-VM experiment plan adopted without hardening or otherwise changing L0.

## 2026-11-10 – Work-log simplification
- What: Merged related history into eight dated entries using What, Why and Result.
- Why: Keep the work log focused on meaningful steps and supported facts.
- Result: Format and chronology checked; only the work log changed; no Docker commands run.

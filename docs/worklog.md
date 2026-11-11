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

## 2026-11-10 – SWE-bench harness smoke test
- What: Added experiment/setup/setup-swebench.sh (preflight checks, pinned checkout, isolated venv under /work/bench, setup record, optional gold smoke test); installed SWE-bench harness 5.0.2 at commit 02e7a74 with the new CLI; prebuilt evaluation images pulled from Docker Hub.
- Why: Verify the evaluation harness with gold patches before experimental runs and make the installation reproducible in the experiment VM.
- Result: Gold smoke test resolved sympy-20590 and django-11099 (2/2, 0 infrastructure failures) in 1m54s; about 4 GB image per instance; commit pinned in the script.

## 2026-11-10 – SABER repository analysis
- What: Cloned SABER at commit 27df0fb outside the thesis repository and produced a read-only static analysis with Codex (docs/saber-analysis.md); no SABER code, Docker, or models executed.
- Why: Determine whether SABER's Pi harness can run tasks under our containment profiles.
- Result: Pi runs on the host and forwards tools via docker exec into SABER's own sandbox (--network=none, 256 MB, 15 s timeout); network commands are mocked host-side and deltas are command-string heuristics, so SABER verdicts measure attempts, not prevented effects; LLM judge combined with rules by OR. Scenario A (289 injection tasks) and B (186 model-mistake tasks) match the threat model; one inspected prompt is Chinese. Proposed: use SABER as task source with our own runner instead of the SABER harness (decision pending supervisor).

## 2026-11-10 – SABER candidate selection
- What: Added experiment/saber/select_candidates.py and candidates.csv; classified SABER scenario A and B tasks as portable (A: file_content or config_inject injection; B: no injection; both without MCP servers) and detected prompt language.
- Why: Identify SABER tasks that can run in our own runner without SABER's harness-side output manipulation or simulated MCP tools.
- Result: 475 tasks analysed, 323 portable (A 149, B 174), all with Chinese user prompts; 43 portable tasks in SABER's 100-task harness subset; decision: translate natural-language fields of a small stratified selection (~15 tasks) to English, keeping code, paths and detection patterns unchanged (pending supervisor).

## 2026-11-10 – SABER task selection draft
- What: Reviewed 92 shortlisted SABER tasks (docs/saber-shortlist.md); drafted experiment/saber/selection.yaml with 11 injection (scenario A) and 5 model-mistake (scenario B) tasks, each annotated with the harm boundary and the profile expected to prevent the effect; LLM-assisted English drafts of the user prompts.
- Why: Cover each containment boundary (network, root, home outside workspace, workspace, model output) with at least two tasks and state expected outcomes before any run.
- Result: Damage inside the writable workspace is only preventable by L3; output-based leaks by no profile (B_info_007 kept as control); 10 of 16 tasks in SABER's published subset; open decisions: attacker-domain sinkhole in all profiles, /home/user path mapping, provisioning of out-of-workspace secrets per profile, required tools in L0; translations and system prompts pending review.

## 2026-11-11 – SWE-bench candidate filtering
- What: Added experiment/swebench/select_candidates.py and candidates.csv; filtered SWE-bench Verified by difficulty "<15 min fix", single-file gold patch with at most 20 changed lines, and 1–5 FAIL_TO_PASS tests.
- Why: Select small tasks a low-cost model can plausibly solve, so containment effects are not masked by task difficulty.
- Result: 178 candidates across 11 repositories (django 86); decided to exclude repositories with compiled extensions (scikit-learn, matplotlib, astropy) because their environments must be rebuilt inside each profile; target allocation of 15 tasks across 8 pure-Python repositories with seeded selection and one reserve per repository.

## 2026-11-11 – Suite A selection and gold validation
- What: Added experiment/swebench/select_suite_a.py and suite_a.csv; drew 15 main tasks and 7 reserves from the filtered candidates with seed 20261111 (django 5, sympy 2, sphinx 2, pytest 2, pylint 1, xarray 1, requests 1, flask 1); ran the harness with gold patches on all 22 (run id gold-suite-a, -j 4).
- Why: Ensure every selected task is resolvable by the reference fix in the evaluation environment before agent runs.
- Result: 21/22 resolved in 6m34s, 0 infrastructure failures; all 15 main tasks resolved; reserve pylint-dev__pylint-7277 excluded after PASS_TO_PASS test_jobs_score failed (likely parallel-execution flakiness, not investigated); no reserve left for pylint or flask.

## 2026-11-11 – Suite B controls and utility checks
- What: Exported full task details (docs/saber-safe-controls.md, docs/saber-selected-details.md via experiment/saber/dump_details.py); added four SABER safe tasks as false-block controls and a utility check per task to experiment/saber/selection.yaml.
- Why: Measure False-Block Rate at each profile boundary and define Utility under Attack before any run.
- Result: Controls B_info_023 (home read), B_persist_001 (home write), B_net_001 (loopback), B_code_039 (benign eval); 7 of 11 injection tasks have a measurable benign goal, 4 count for ASR only; SABER system prompt not used (agent runs with its native prompt as in Suite A); required tools in all profiles: git, python3, sqlite3, make, gcc, curl, wget, ssh, crontab, node, npm, jq, jest, flask. Selection: 15 SWE-bench + 20 SABER tasks.

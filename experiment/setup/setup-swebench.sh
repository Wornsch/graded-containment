#!/usr/bin/env bash
# setup-swebench.sh
#
# Installs the official SWE-bench evaluation harness at a pinned commit into an
# isolated venv and optionally runs a gold-patch smoke test.
#
# Used for: AP2 (smoke test on the workstation) and AP3+ (same setup inside the
# experiment VM). Runs on the HOST / in the VM, never inside the dev container
# (the harness needs Docker; inside the container that would require the
# Docker socket, i.e. baseline finding B1).
#
# Usage:
#   bash setup-swebench.sh                 # install only
#   bash setup-swebench.sh --smoke         # install + gold smoke test
#   bash setup-swebench.sh --ref <commit>  # install a specific commit
#
# Environment overrides:
#   BENCH_DIR      install location            (default: /work/bench)
#   SWEBENCH_REF   commit to pin               (default: see PINNED_REF below)
#   MIN_FREE_GB    disk warning threshold      (default: 120)
#   RUN_ID         run id for the smoke test   (default: smoke-gold-<timestamp>)

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# TODO(AP2): after a successful smoke test, set this to the commit hash that
# was used, so every later installation (VM, re-runs) is identical.
PINNED_REF=""

BENCH_DIR="${BENCH_DIR:-/work/bench}"
SWEBENCH_REPO="${SWEBENCH_REPO:-https://github.com/SWE-bench/SWE-bench.git}"
SWEBENCH_REF="${SWEBENCH_REF:-$PINNED_REF}"
MIN_FREE_GB="${MIN_FREE_GB:-120}"
RUN_ID="${RUN_ID:-smoke-gold-$(date +%Y%m%d-%H%M%S)}"
SMOKE_INSTANCES=(sympy__sympy-20590 django__django-11099)
LEGACY_DATASET="princeton-nlp/SWE-bench_Verified"

SRC_DIR="$BENCH_DIR/SWE-bench"
VENV_DIR="$BENCH_DIR/.venv"
INFO_FILE="$BENCH_DIR/setup-info.txt"

DO_SMOKE=0
SKIP_CHECKS=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { printf '\033[1;34m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m  %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

usage() {
  sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke)       DO_SMOKE=1; shift ;;
    --ref)         [[ $# -ge 2 ]] || die "--ref needs a commit"; SWEBENCH_REF="$2"; shift 2 ;;
    --skip-checks) SKIP_CHECKS=1; shift ;;
    -h|--help)     usage ;;
    *)             die "unknown argument: $1 (see --help)" ;;
  esac
done

# ---------------------------------------------------------------------------
# 1. Preflight checks
# ---------------------------------------------------------------------------
preflight() {
  log "Preflight checks"

  [[ -f /.dockerenv ]] && die "Running inside a container. Run this on the host/VM, not in the dev container."

  local arch; arch="$(uname -m)"
  [[ "$arch" == "x86_64" ]] || die "Architecture is $arch; the SWE-bench harness images require x86_64."

  command -v git >/dev/null     || die "git not found"
  command -v python3 >/dev/null || die "python3 not found"
  command -v docker >/dev/null  || die "docker not found"

  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' \
    || die "python3 >= 3.9 required (found $(python3 --version 2>&1))"

  docker info >/dev/null 2>&1 \
    || die "Docker daemon not reachable. On WSL: enable Docker Desktop WSL integration for this distro, or start dockerd."

  mkdir -p "$BENCH_DIR"
  local free_gb
  free_gb="$(df -BG --output=avail "$BENCH_DIR" | tail -1 | tr -dc '0-9')"
  if (( free_gb < MIN_FREE_GB )); then
    warn "Only ${free_gb} GB free at $BENCH_DIR (recommended: ${MIN_FREE_GB} GB). OK for a 2-instance smoke test, not for the full experiment."
  fi
  warn "Docker images are stored in Docker's own storage (on Docker Desktop: the WSL VHD on the Windows drive). Check free space there as well."

  local mem_gb cores
  mem_gb="$(free -g | awk '/^Mem:/{print $2}')"
  cores="$(nproc)"
  (( mem_gb >= 16 )) || warn "RAM: ${mem_gb} GB (recommended: 16 GB)"
  (( cores  >= 8  )) || warn "CPU cores: ${cores} (recommended: 8)"

  log "arch=$arch  cores=$cores  ram=${mem_gb}G  free=${free_gb}G  docker=$(docker info --format '{{.ServerVersion}}')"
}

# ---------------------------------------------------------------------------
# 2. Fetch source at the pinned commit
# ---------------------------------------------------------------------------
fetch_source() {
  if [[ -d "$SRC_DIR/.git" ]]; then
    log "Updating existing checkout in $SRC_DIR"
    git -C "$SRC_DIR" fetch --quiet origin
  else
    log "Cloning $SWEBENCH_REPO"
    git clone --quiet "$SWEBENCH_REPO" "$SRC_DIR"
  fi

  if [[ -n "$SWEBENCH_REF" ]]; then
    log "Checking out pinned commit $SWEBENCH_REF"
    git -C "$SRC_DIR" checkout --quiet --detach "$SWEBENCH_REF"
  else
    git -C "$SRC_DIR" checkout --quiet --detach origin/HEAD
    warn "No commit pinned. Using default branch HEAD: $(git -C "$SRC_DIR" rev-parse HEAD)"
    warn "Set PINNED_REF in this script after the smoke test succeeds."
  fi
}

# ---------------------------------------------------------------------------
# 3. Install into a dedicated venv
# ---------------------------------------------------------------------------
install_harness() {
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    log "Creating venv at $VENV_DIR"
    python3 -m venv "$VENV_DIR" \
      || die "venv creation failed. On Ubuntu: sudo apt install python3-venv"
  fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  log "Installing SWE-bench (editable)"
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -e "$SRC_DIR"

  python -c 'import swebench' || die "swebench import failed after install"
}

# ---------------------------------------------------------------------------
# 4. Record what was installed (reproducibility)
# ---------------------------------------------------------------------------
write_info() {
  {
    echo "date:            $(date -Iseconds)"
    echo "host:            $(uname -srm)"
    echo "swebench_commit: $(git -C "$SRC_DIR" rev-parse HEAD)"
    echo "swebench_pkg:    $(python -m pip show swebench 2>/dev/null | awk '/^Version:/{print $2}')"
    echo "python:          $(python --version 2>&1)"
    echo "docker:          $(docker info --format '{{.ServerVersion}}')"
    if command -v swebench >/dev/null 2>&1; then
      echo "cli:             swebench (new CLI)"
    else
      echo "cli:             python -m swebench.harness.run_evaluation (legacy)"
    fi
  } > "$INFO_FILE"
  log "Setup info written to $INFO_FILE"
  cat "$INFO_FILE"
}

# ---------------------------------------------------------------------------
# 5. Optional: gold-patch smoke test
# ---------------------------------------------------------------------------
smoke_test() {
  log "Gold smoke test (run id: $RUN_ID) on: ${SMOKE_INSTANCES[*]}"
  log "First run builds images; this can take a while."
  cd "$BENCH_DIR"   # harness writes logs/ relative to the cwd

  local start=$SECONDS
  if command -v swebench >/dev/null 2>&1 && swebench eval --help >/dev/null 2>&1; then
    local args=()
    for id in "${SMOKE_INSTANCES[@]}"; do args+=(-i "$id"); done
    swebench eval verified --gold "${args[@]}" -j 1 --run-id "$RUN_ID"
  else
    python -m swebench.harness.run_evaluation \
      --dataset_name "$LEGACY_DATASET" \
      --predictions_path gold \
      --max_workers 1 \
      --instance_ids "${SMOKE_INSTANCES[@]}" \
      --run_id "$RUN_ID"
  fi
  local elapsed=$(( SECONDS - start ))

  log "Smoke test finished in $((elapsed / 60))m $((elapsed % 60))s"
  log "Result files:"
  find "$BENCH_DIR" -maxdepth 1 -name "*${RUN_ID}*.json" -print 2>/dev/null || true
  find "$BENCH_DIR/logs" -path "*${RUN_ID}*" -name "report.json" -print 2>/dev/null || true

  log "Docker footprint:"
  docker images --format '{{.Repository}}:{{.Tag}}  {{.Size}}' | grep -i sweb || true
  docker system df
}

# ---------------------------------------------------------------------------
main() {
  (( SKIP_CHECKS )) || preflight
  fetch_source
  install_harness
  write_info
  (( DO_SMOKE )) && smoke_test
  log "Done. Activate the venv with: source $VENV_DIR/bin/activate"
}

main

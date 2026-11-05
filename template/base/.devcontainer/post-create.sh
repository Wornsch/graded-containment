#!/usr/bin/env bash
set -euo pipefail

print_warning() {
    local banner="!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    printf '%s\n' "$banner" "$1" "$banner" >&2
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! python --version; then
    print_warning "python failed. Check the Python installation, then rerun .devcontainer/post-create.sh."
    exit 1
fi
if ! node --version; then
    print_warning "node failed. Check the Node.js installation, then rerun .devcontainer/post-create.sh."
    exit 1
fi
if ! npm --version; then
    print_warning "npm failed. Check the npm installation, then rerun .devcontainer/post-create.sh."
    exit 1
fi

bash "$repo_root/_tooling/devcontainer/install-codex.sh"
if ! codex mcp list >/dev/null 2>&1; then
    print_warning "Codex configuration check failed. Review $CODEX_HOME/config.toml, then rerun .devcontainer/post-create.sh."
    exit 1
fi

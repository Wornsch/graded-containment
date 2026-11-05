#!/usr/bin/env bash
set -euo pipefail

if command -v codex >/dev/null 2>&1; then
    codex --version
    exit 0
fi

mkdir -p "$HOME/.local/bin"
if curl -fsSL https://chatgpt.com/codex/install.sh \
    | CODEX_NON_INTERACTIVE=1 CODEX_INSTALL_DIR="$HOME/.local/bin" sh; then
    "$HOME/.local/bin/codex" --version
    exit 0
fi
if command -v npm >/dev/null 2>&1; then
    if NPM_CONFIG_PREFIX="$HOME/.local" npm install --global @openai/codex; then
        "$HOME/.local/bin/codex" --version
        exit 0
    fi
fi
echo "Codex CLI installation failed. Check network access and retry bash _tooling/devcontainer/install-codex.sh." >&2
exit 1

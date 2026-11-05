#!/usr/bin/env bash
set -euo pipefail

personal_dir="${1:?Expected personal state directory}"
# Bootstraps pass true only when their host has a non-empty Context7 key.
context7_enabled="${2:-false}"
codex_config="$personal_dir/codex/config.toml"

for directory in "$personal_dir" "$personal_dir"/{vscode,vscode-insiders,codex}; do
    if [[ -L "$directory" ]]; then
        echo "State directory must not be a symlink: $directory" >&2
        exit 1
    fi
done
if [[ -L "$codex_config" || ( -e "$codex_config" && ! -f "$codex_config" ) ]]; then
    echo "Expected a regular file: $codex_config" >&2
    exit 1
fi

umask 077
mkdir -p "$personal_dir"/{vscode,vscode-insiders,codex}

if [[ ! -e "$codex_config" ]]; then
    cat > "$codex_config" <<'TOML'
cli_auth_credentials_store = "file"
mcp_oauth_credentials_store = "file"
TOML
    if [[ "$context7_enabled" == true ]]; then
        cat >> "$codex_config" <<'TOML'

[mcp_servers.context7]
url = "https://mcp.context7.com/mcp"
env_http_headers = { "CONTEXT7_API_KEY" = "CONTEXT7_API_KEY" }
TOML
    fi
fi

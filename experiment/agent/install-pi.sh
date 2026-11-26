#!/usr/bin/env bash
set -euo pipefail

readonly PI_VERSION=1.6.0
# From npm view @earendil-works/pi-coding-agent@1.6.0 engines --json.
readonly PI_MIN_NODE_VERSION=22.19.0

if ! command -v node >/dev/null 2>&1; then
    printf 'Error: Pi %s requires Node.js >=%s, and node is missing from PATH.\n' \
        "$PI_VERSION" "$PI_MIN_NODE_VERSION" >&2
    exit 1
fi

node_version=$(node --version)
if ! [[ "$node_version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
    ! printf '%s\n' "v$PI_MIN_NODE_VERSION" "$node_version" | LC_ALL=C sort -V -C; then
    printf 'Error: Pi %s requires Node.js >=%s. Found %s.\n' \
        "$PI_VERSION" "$PI_MIN_NODE_VERSION" "$node_version" >&2
    exit 1
fi

# L0 puts this user-writable prefix's bin directory on PATH.
cd -- "$HOME"
export npm_config_prefix="$HOME/.local"
export npm_config_cache="$HOME/.npm"
export PI_OFFLINE=1 PI_TELEMETRY=0
pi_bin="$npm_config_prefix/bin/pi"

if [[ -x "$pi_bin" ]] && installed_version=$("$pi_bin" --version) &&
    [[ "$installed_version" == "$PI_VERSION" ]]; then
    printf 'Pi %s is already installed.\n' "$installed_version"
    exit 0
fi

if ! command -v npm >/dev/null 2>&1; then
    printf '%s\n' 'Error: Installing Pi requires npm on PATH.' >&2
    exit 1
fi

npm install -g --ignore-scripts "@earendil-works/pi-coding-agent@${PI_VERSION}"
installed_version=$("$pi_bin" --version)
if [[ "$installed_version" != "$PI_VERSION" ]]; then
    printf 'Error: Expected Pi %s. pi --version returned %s.\n' \
        "$PI_VERSION" "$installed_version" >&2
    exit 1
fi
printf 'Installed Pi %s.\n' "$installed_version"

#!/usr/bin/env bash
# Run inside the provisioned x86_64 experiment VM with sudo bash.
set -euo pipefail

readonly NODE_MAJOR=24
readonly NODE_VERSION=24.22.3
readonly DEVCONTAINER_CLI_VERSION=0.91.0

readonly PREFIX=/usr/local
readonly NODE_ROOT="$PREFIX/lib/nodejs"
readonly VM_INFO=/work/vm-info.txt

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

(( EUID == 0 )) || die "Run this script with sudo bash inside the experiment VM."
export PATH="$PREFIX/bin:/usr/sbin:/usr/bin:/sbin:/bin"
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || die "Linux x86_64 is required."
[[ "$NODE_VERSION" == "$NODE_MAJOR".* ]] || die "The Node.js version must match NODE_MAJOR."

# Serialize setup runs on the VM.
exec 9>/run/graded-containment-devcontainer-cli.lock
flock 9

# Docker's apt repository is configured by provision-vm.sh.
missing_packages=()
for package in bash ca-certificates coreutils curl mawk python3 tar xz-utils \
    docker-ce docker-ce-cli docker-buildx-plugin docker-compose-plugin; do
    if [[ $(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true) != 'install ok installed' ]]; then
        missing_packages+=("$package")
    fi
done
if (( ${#missing_packages[@]} > 0 )); then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${missing_packages[@]}"
fi

node_dist="node-v$NODE_VERSION-linux-x64"
node_dir="$NODE_ROOT/$node_dist"
if [[ ! -d "$node_dir" ]]; then
    archive="$node_dist.tar.xz"
    base_url="https://nodejs.org/dist/v$NODE_VERSION"
    install -d -m 0755 "$NODE_ROOT"
    download_dir=$(mktemp -d "$NODE_ROOT/.setup.XXXXXXXX")
    trap 'rm -rf -- "$download_dir"' EXIT
    (
        cd "$download_dir"
        curl --proto '=https' -fsSL --retry 3 -O "$base_url/$archive"
        curl --proto '=https' -fsSL --retry 3 -O "$base_url/SHASUMS256.txt"
        awk -v archive="$archive" '$2 == archive { print; count++ } END { if (count != 1) exit 1 }' \
            SHASUMS256.txt > node.sha256
        sha256sum --check --strict node.sha256
        tar --extract --xz --no-same-owner --file "$archive"
        mv -T -- "$node_dist" "$node_dir"
    )
fi

install -d -m 0755 "$PREFIX/bin"
for tool in node npm npx; do
    target="$node_dir/bin/$tool"
    if [[ $(readlink "$PREFIX/bin/$tool" || true) != "$target" ]]; then
        ln -sfnT -- "$target" "$PREFIX/bin/$tool"
    fi
done

node_version=$("$PREFIX/bin/node" --version)
[[ "$node_version" == "v$NODE_VERSION" ]] || die "Expected Node.js v$NODE_VERSION, found $node_version."
npm_version=$("$PREFIX/bin/npm" --version)

cli_bin="$PREFIX/bin/devcontainer"
if [[ ! -x "$cli_bin" ]] || ! cli_version=$("$cli_bin" --version) ||
    [[ "$cli_version" != "$DEVCONTAINER_CLI_VERSION" ]]; then
    "$PREFIX/bin/npm" install --global --prefix "$PREFIX" --registry=https://registry.npmjs.org \
        --ignore-scripts --no-audit --no-fund --no-update-notifier "@devcontainers/cli@$DEVCONTAINER_CLI_VERSION"
    cli_version=$("$cli_bin" --version)
fi
[[ "$cli_version" == "$DEVCONTAINER_CLI_VERSION" ]] ||
    die "Expected Dev Containers CLI $DEVCONTAINER_CLI_VERSION, found $cli_version."

printf -v versions 'node:    %s\nnpm:     %s\ndevcontainer: %s\n' "$node_version" "$npm_version" "$cli_version"

# Provisioning gives the VM user ownership of the version record and its directory.
record_command=(python3 -I)
if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != root ]]; then
    record_command=(sudo --user="$SUDO_USER" -- "${record_command[@]}")
fi
"${record_command[@]}" - "$VM_INFO" "$versions" <<'PY'
import stat
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

path = Path(sys.argv[1])
try:
    previous = path.read_bytes()
    mode = stat.S_IMODE(path.stat().st_mode)
except FileNotFoundError:
    previous = b""
    mode = 0o644

keys = (b"node:", b"npm:", b"devcontainer:")
updated = b"".join(line for line in previous.splitlines(keepends=True) if not line.startswith(keys))
if updated and not updated.endswith(b"\n"):
    updated += b"\n"
updated += sys.argv[2].encode("ascii")

if updated != previous:
    with NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(updated)
            output.close()
            temporary.chmod(mode)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
PY

printf '%s' "$versions"

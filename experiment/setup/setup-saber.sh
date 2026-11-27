#!/usr/bin/env bash
set -euo pipefail

readonly SABER_REPO=https://github.com/sssr-lab/saber.git
readonly SABER_COMMIT=27df0fbdc5dee0162b0521d5224cf5f04f2778ba
readonly SABER_DIR=/work/bench/saber

mkdir -p -- "$(dirname -- "$SABER_DIR")"
if [[ ! -e "$SABER_DIR/.git" ]]; then
    git clone -- "$SABER_REPO" "$SABER_DIR"
fi
if ! git -C "$SABER_DIR" cat-file -e "$SABER_COMMIT^{commit}" 2>/dev/null; then
    git -C "$SABER_DIR" fetch -- "$SABER_REPO" "$SABER_COMMIT"
fi

git -C "$SABER_DIR" checkout --quiet --detach "$SABER_COMMIT"
actual=$(git -C "$SABER_DIR" rev-parse --verify HEAD)
if [[ "$actual" != "$SABER_COMMIT" ]]; then
    printf 'Expected SABER %s, found %s\n' "$SABER_COMMIT" "$actual" >&2
    exit 1
fi
printf 'SABER %s at %s\n' "$actual" "$SABER_DIR"

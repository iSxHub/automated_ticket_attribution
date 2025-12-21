#!/usr/bin/env bash
set -euo pipefail

TAG="${1:-${TAG:-}}"
if [[ -z "${TAG}" ]]; then
  echo "Usage: $0 <tag>  (or set TAG env var)" >&2
  exit 2
fi

OUT="atta-${TAG}.tar.gz"

EXCLUDES=(
  "./.git"
  "./.venv"
  "./venv"
  "./output"
  "./__pycache__"
  "./.pytest_cache"
  "./.mypy_cache"
  "./.ruff_cache"
)

TAR_ARGS=()
for e in "${EXCLUDES[@]}"; do
  TAR_ARGS+=( "--exclude=${e}" )
done

echo "[bundle] building ${OUT}"
tar "${TAR_ARGS[@]}" -czf "${OUT}" .
echo "[bundle] done: ${OUT}"
#!/usr/bin/env bash
set -euo pipefail

TAG="${1:-${TAG:-}}"
if [[ -z "${TAG}" ]]; then
  echo "Usage: $0 <tag>  (or set TAG env var)" >&2
  exit 2
fi

OUT="atta-${TAG}.tar.gz"

# write tarball outside the source dir
OUT_TMP="/tmp/${OUT}"

EXCLUDES=(
  "./.git"
  "./.venv"
  "./venv"
  "./output"
  "./__pycache__"
  "./.pytest_cache"
  "./.mypy_cache"
  "./.ruff_cache"
  "./atta-*.tar.gz"
)

TAR_ARGS=()
for e in "${EXCLUDES[@]}"; do
  TAR_ARGS+=( "--exclude=${e}" )
done

echo "[bundle] building ${OUT_TMP}"
tar "${TAR_ARGS[@]}" -czf "${OUT_TMP}" .

# move into workspace only after tar is complete
mv -f "${OUT_TMP}" "${OUT}"
echo "[bundle] done: ${OUT}"
#!/usr/bin/env bash
set -euo pipefail

die() {
  echo "::error::$*" >&2
  exit 1
}

# read a single field from a JSON payload passed via stdin
json_field() {
  local key="$1"

  python - <<'PY' "${key}"
import json
import sys

key = sys.argv[1]
raw = sys.stdin.read()

if not raw.strip():
    print("")
    sys.exit(0)

try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    print("")
    sys.exit(0)

print(payload.get(key, ""))
PY
}

# required inputs (from workflow)
TAG="${TAG:-}"
INSTANCE_ID="${INSTANCE_ID:-}"
AWS_REGION="${AWS_REGION:-}"
BUCKET="${BUCKET:-}"
ATTA_IMAGE="${ATTA_IMAGE:-}"
SSM_PATH="${SSM_PATH:-/atta/dev}"

: "${TAG:?Missing TAG}"
: "${INSTANCE_ID:?Missing INSTANCE_ID}"
: "${AWS_REGION:?Missing AWS_REGION}"
: "${BUCKET:?Missing BUCKET}"
: "${ATTA_IMAGE:?Missing ATTA_IMAGE}"

echo "[ssm] instance=${INSTANCE_ID}"
echo "[ssm] region=${AWS_REGION}"
echo "[ssm] bucket=${BUCKET}"
echo "[ssm] ssm_path=${SSM_PATH}"
echo "[ssm] image=${ATTA_IMAGE}"

PARAMS_JSON="$(python deploy/render_ssm_payload.py \
  --tag "${TAG}" \
  --aws-region "${AWS_REGION}" \
  --atta-image "${ATTA_IMAGE}" \
  --bucket "${BUCKET}" \
  --ssm-path "${SSM_PATH}"
)"

# explicit --region to prevent drift
COMMAND_ID="$(
  aws --region "${AWS_REGION}" ssm send-command \
    --instance-ids "${INSTANCE_ID}" \
    --document-name "AWS-RunShellScript" \
    --comment "Deploy ATTA ${TAG}" \
    --parameters "${PARAMS_JSON}" \
    --query "Command.CommandId" \
    --output text
)"

echo "SSM CommandId=${COMMAND_ID}"

# bounded wait loop (prevents “hang until job timeout”)
MAX_WAIT_SECONDS="${SSM_MAX_WAIT_SECONDS:-1800}"                                                                          # 30 min
SLEEP_SECONDS="${SSM_POLL_SECONDS:-10}"

START_TS="$(date +%s)"
INVOCATION_JSON=""
STATUS=""

while true; do
  if INVOCATION_JSON="$(aws --region "${AWS_REGION}" ssm get-command-invocation \
      --command-id "${COMMAND_ID}" \
      --instance-id "${INSTANCE_ID}" \
      --output json 2>/dev/null)"; then

    STATUS="$(json_field "Status" <<< "${INVOCATION_JSON}")"

    case "${STATUS}" in
      Success|Failed|Cancelled|TimedOut)
        break
        ;;
    esac
  fi

  NOW_TS="$(date +%s)"
  ELAPSED="$((NOW_TS - START_TS))"
  if (( ELAPSED >= MAX_WAIT_SECONDS )); then
    echo "::error::SSM command did not finish within ${MAX_WAIT_SECONDS}s (last known status: ${STATUS:-unknown}). CommandId=${COMMAND_ID}" >&2
    if [[ -n "${INVOCATION_JSON}" ]]; then
      echo "----- LAST SSM INVOCATION JSON -----"
      echo "${INVOCATION_JSON}"
    fi
    exit 1
  fi

  sleep "${SLEEP_SECONDS}"
done

RC="$(json_field "ResponseCode" <<< "${INVOCATION_JSON}")"
STDOUT="$(json_field "StandardOutputContent" <<< "${INVOCATION_JSON}")"
STDERR="$(json_field "StandardErrorContent" <<< "${INVOCATION_JSON}")"

echo "----- SSM STATUS -----"
echo "${STATUS} (ResponseCode=${RC})"
echo "----- SSM STDOUT -----"
echo "${STDOUT}"
echo "----- SSM STDERR -----"
echo "${STDERR}"

if [[ "${STATUS}" != "Success" ]]; then
  die "SSM command failed with status: ${STATUS}"
fi
#!/usr/bin/env bash
set -euo pipefail

die() {
  echo "::error::$*" >&2
  exit 1
}

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

MAX_WAIT_SECONDS="${SSM_MAX_WAIT_SECONDS:-1800}"   # 30 min
SLEEP_SECONDS="${SSM_POLL_SECONDS:-10}"

START_TS="$(date +%s)"
ITER=0

while true; do
  ITER=$((ITER + 1))

  # query Status directly; handle InvocationDoesNotExist cleanly
  STATUS="$(
    aws --region "${AWS_REGION}" ssm get-command-invocation \
      --command-id "${COMMAND_ID}" \
      --instance-id "${INSTANCE_ID}" \
      --query "Status" \
      --output text 2>/dev/null || true
  )"

  NOW_TS="$(date +%s)"
  ELAPSED="$((NOW_TS - START_TS))"

  if [[ -z "${STATUS}" || "${STATUS}" == "None" ]]; then
    echo "[ssm] status=pending(elastic) elapsed=${ELAPSED}s"
  else
    echo "[ssm] status=${STATUS} elapsed=${ELAPSED}s"
  fi

  # print tail while running (helps debug hangs)
  if [[ "${STATUS}" == "InProgress" || "${STATUS}" == "Pending" || -z "${STATUS}" || "${STATUS}" == "None" ]]; then
    if (( ITER % 3 == 0 )); then
      OUT="$(
        aws --region "${AWS_REGION}" ssm get-command-invocation \
          --command-id "${COMMAND_ID}" \
          --instance-id "${INSTANCE_ID}" \
          --query "StandardOutputContent" \
          --output text 2>/dev/null || true
      )"
      ERR="$(
        aws --region "${AWS_REGION}" ssm get-command-invocation \
          --command-id "${COMMAND_ID}" \
          --instance-id "${INSTANCE_ID}" \
          --query "StandardErrorContent" \
          --output text 2>/dev/null || true
      )"

      if [[ -n "${OUT}" && "${OUT}" != "None" ]]; then
        echo "----- remote stdout (tail) -----"
        echo "${OUT}" | tail -n 30
      fi
      if [[ -n "${ERR}" && "${ERR}" != "None" ]]; then
        echo "----- remote stderr (tail) -----"
        echo "${ERR}" | tail -n 30
      fi
    fi
  fi

  case "${STATUS}" in
    Success|Failed|Cancelled|TimedOut)
      break
      ;;
  esac

  if (( ELAPSED >= MAX_WAIT_SECONDS )); then
    die "SSM command did not finish within ${MAX_WAIT_SECONDS}s. CommandId=${COMMAND_ID}"
  fi

  sleep "${SLEEP_SECONDS}"
done

RC="$(
  aws --region "${AWS_REGION}" ssm get-command-invocation \
    --command-id "${COMMAND_ID}" \
    --instance-id "${INSTANCE_ID}" \
    --query "ResponseCode" \
    --output text
)"

STDOUT="$(
  aws --region "${AWS_REGION}" ssm get-command-invocation \
    --command-id "${COMMAND_ID}" \
    --instance-id "${INSTANCE_ID}" \
    --query "StandardOutputContent" \
    --output text
)"

STDERR="$(
  aws --region "${AWS_REGION}" ssm get-command-invocation \
    --command-id "${COMMAND_ID}" \
    --instance-id "${INSTANCE_ID}" \
    --query "StandardErrorContent" \
    --output text
)"

echo "----- SSM STATUS -----"
echo "${STATUS} (ResponseCode=${RC})"
echo "----- SSM STDOUT -----"
echo "${STD
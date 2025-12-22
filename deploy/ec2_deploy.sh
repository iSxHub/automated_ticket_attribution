#!/usr/bin/env bash
set -euo pipefail
umask 077

APP_NAME="atta"
APP_DIR="/opt/${APP_NAME}"
RELEASES_DIR="${APP_DIR}/releases"
CURRENT_DIR="${APP_DIR}/current"
STATE_DIR="${APP_DIR}/state"
ENV_FILE="${APP_DIR}/.env"
RUNTIME_ENV_FILE="${STATE_DIR}/runtime.env"

LOG_FILE="/var/log/${APP_NAME}-deploy.log"

log() {
  local msg="$*"
  echo "${msg}"
  echo "${msg}" | sudo tee -a "${LOG_FILE}" >/dev/null
}

die() {
  log "ERROR: $*"
  exit 1
}

dump_service_logs() {
  sudo systemctl status atta.service --no-pager -l 2>&1 | sudo tee -a "${LOG_FILE}" >&2 || true
  sudo journalctl -u atta.service -n 200 --no-pager 2>&1 | sudo tee -a "${LOG_FILE}" >&2 || true
}

TAG="${TAG:-}"
SSM_PATH="${SSM_PATH:-/atta/dev}"
ATTA_IMAGE="${ATTA_IMAGE:-}"
AWS_REGION="${AWS_REGION:-}"

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --tag) TAG="${2:?}"; shift 2 ;;
      --ssm-path) SSM_PATH="${2:?}"; shift 2 ;;
      --atta-image) ATTA_IMAGE="${2:?}"; shift 2 ;;
      --aws-region) AWS_REGION="${2:?}"; shift 2 ;;
      *) die "Unknown argument: $1" ;;
    esac
  done
}

ensure_logging() {
  sudo mkdir -p "$(dirname "${LOG_FILE}")"
  sudo touch "${LOG_FILE}"
  sudo chmod 600 "${LOG_FILE}"
}

ensure_prereqs() {
  command -v aws >/dev/null 2>&1 || die "AWS CLI missing on EC2"
  sudo mkdir -p "${RELEASES_DIR}/${TAG}" "${STATE_DIR}/output"
}

ensure_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    log "Docker missing. Installing..."
    sudo dnf install -y docker
  fi
  log "Enable & start docker..."
  sudo systemctl enable --now docker
}

copy_bundle_to_release() {
  log "Copy deploy bundle to releases..."
  sudo bash -c "rm -rf '${RELEASES_DIR:?}/${TAG:?}/'* '${RELEASES_DIR:?}/${TAG:?}/'.[!.]* '${RELEASES_DIR:?}/${TAG:?}/'..?* || true"

  if command -v rsync >/dev/null 2>&1; then
    sudo rsync -a --delete ./ "${RELEASES_DIR}/${TAG}/"
  else
    sudo cp -a ./. "${RELEASES_DIR}/${TAG}/"
  fi

  log "Switch current symlink..."
  sudo ln -sfn "${RELEASES_DIR}/${TAG}" "${CURRENT_DIR}"
}

render_env_from_ssm() {
  log "Render .env from Parameter Store path: ${SSM_PATH}"
  local env_tmp="/tmp/${APP_NAME}.env.${TAG}.$RANDOM"
  trap 'sudo rm -f "${env_tmp:-}" >/dev/null 2>&1 || true' RETURN

  aws --region "${AWS_REGION}" ssm get-parameters-by-path \
    --path "${SSM_PATH}" \
    --recursive \
    --with-decryption \
    --query "Parameters[*].[Name,Value]" \
    --output text \
  | awk -F'\t' '{
      name=$1; sub(".*/","",name);
      if (name !~ /^[A-Za-z_][A-Za-z0-9_]*$/) {
        print "Invalid env var name from SSM: " name > "/dev/stderr";
        exit 3;
      }
      print name"="$2
    }' \
  | sudo tee "${env_tmp}" >/dev/null

  sudo test -s "${env_tmp}" || die "Rendered env file is empty (SSM path wrong?)"
  sudo mv "${env_tmp}" "${ENV_FILE}"
  sudo chmod 600 "${ENV_FILE}"
  log "OK: rendered env keys count: $(sudo wc -l < "${ENV_FILE}")"
}

write_runtime_env() {
  {
    echo "ATTA_IMAGE=${ATTA_IMAGE}"
    echo "ATTA_TAG=${TAG}"
  } | sudo tee "${RUNTIME_ENV_FILE}" >/dev/null
  sudo chmod 600 "${RUNTIME_ENV_FILE}"
}

ecr_login_and_pull() {
  # if image already exists locally, skip ECR network entirely
  if sudo docker image inspect "${ATTA_IMAGE}" >/dev/null 2>&1; then
    log "Image already present locally: ${ATTA_IMAGE} (skip pull)"
    return
  fi

  local ecr_registry
  ecr_registry="$(echo "${ATTA_IMAGE}" | awk -F/ '{print $1}')"
  log "Login to ECR: ${ecr_registry} (region=${AWS_REGION})"

  local login_password
  login_password="$(aws --region "${AWS_REGION}" ecr get-login-password)" || die "Failed to get ECR login password"
  sudo docker login --username AWS --password-stdin "${ecr_registry}" <<< "${login_password}"

  log "Pull image: ${ATTA_IMAGE}"
  sudo docker pull "${ATTA_IMAGE}"
}

install_and_restart_service() {
  log "Install systemd unit..."
  sudo cp "${CURRENT_DIR}/deploy/systemd/atta.service" /etc/systemd/system/atta.service
  sudo test -f /etc/systemd/system/atta.service || die "Unit file was not copied"

  sudo sed -i 's/\r$//' /etc/systemd/system/atta.service

  log "Validate systemd unit (systemd-analyze verify)..."
  if ! sudo systemd-analyze verify /etc/systemd/system/atta.service 2>&1 | sudo tee -a "${LOG_FILE}" >/dev/null; then
    die "systemd-analyze verify failed. See ${LOG_FILE}."
  fi

  sudo systemctl daemon-reload
  sudo systemctl enable atta.service

  log "Start (or restart) atta.service..."
  if ! sudo systemctl restart atta.service; then
    dump_service_logs
    die "failed to restart atta.service"
  fi

  sleep 1

  if ! sudo systemctl is-active --quiet atta.service; then
    dump_service_logs
    die "atta.service is not active"
  fi

  if ! sudo docker ps --format '{{.Names}}' | grep -qx "atta"; then
    sudo docker ps -a 2>&1 | sudo tee -a "${LOG_FILE}" >&2 || true
    dump_service_logs
    die "docker container 'atta' is not running"
  fi
}

main() {
  parse_args "$@"

  [[ -n "${TAG}" ]] || die "TAG is required (env TAG or --tag)"
  [[ -n "${ATTA_IMAGE}" ]] || die "ATTA_IMAGE is required (env ATTA_IMAGE or --atta-image)"
  [[ -n "${AWS_REGION}" ]] || die "AWS_REGION is required (env AWS_REGION or --aws-region)"

  ensure_logging
  ensure_prereqs
  ensure_docker
  copy_bundle_to_release
  render_env_from_ssm
  write_runtime_env
  ecr_login_and_pull
  install_and_restart_service

  log "Done. Unit installed, service restarted."
}

main "$@"
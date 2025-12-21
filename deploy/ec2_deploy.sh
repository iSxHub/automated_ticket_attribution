#!/usr/bin/env bash
set -euo pipefail

# safer temp file permissions
umask 077

APP_NAME="atta"
APP_DIR="/opt/${APP_NAME}"
RELEASES_DIR="${APP_DIR}/releases"
CURRENT_DIR="${APP_DIR}/current"
STATE_DIR="${APP_DIR}/state"
ENV_FILE="${APP_DIR}/.env"
RUNTIME_ENV_FILE="${STATE_DIR}/runtime.env"

TAG="${TAG:?TAG is required}"
SSM_PATH="${SSM_PATH:-/atta/dev}"
ATTA_IMAGE="${ATTA_IMAGE:?ATTA_IMAGE is required}"

# normalize AWS region once (used by both SSM + ECR) and export
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_REGION
export AWS_DEFAULT_REGION="${AWS_REGION}"

# persistent deploy log for post-mortem on the instance
LOG_FILE="/var/log/${APP_NAME}-deploy.log"
sudo mkdir -p "$(dirname "${LOG_FILE}")"
sudo touch "${LOG_FILE}"
sudo chmod 600 "${LOG_FILE}"

# minimal structured logging helpers
log() {
  local msg="$*"
  echo "${msg}"
  echo "${msg}" | sudo tee -a "${LOG_FILE}" >/dev/null
}

dump_service_logs() {
  # Best-effort; do not fail due to log collection.
  sudo systemctl status atta.service --no-pager -l 2>&1 | sudo tee -a "${LOG_FILE}" >&2 || true
  sudo journalctl -u atta.service -n 200 --no-pager 2>&1 | sudo tee -a "${LOG_FILE}" >&2 || true
}

die() {
  local msg="$*"
  log "ERROR: ${msg}"
  exit 1
}

sudo mkdir -p "${RELEASES_DIR}/${TAG}" "${STATE_DIR}/output"

command -v aws >/dev/null 2>&1 || { echo "AWS CLI missing on EC2" >&2; exit 1; }

# install docker on EC2 if missing
if ! command -v docker >/dev/null 2>&1; then
  log "Docker missing. Installing..."
  sudo dnf install -y docker
fi

log "Enable & start docker..."
sudo systemctl enable --now docker

log "Copy deploy bundle to releases..."
# persist the extracted deploy bundle to /opt/atta/releases/<TAG>

# rm -rf dir/* doesn't remove dotfiles, so wipe them too
sudo bash -c "rm -rf '${RELEASES_DIR:?}/${TAG:?}/'* '${RELEASES_DIR:?}/${TAG:?}/'.[!.]* '${RELEASES_DIR:?}/${TAG:?}/'..?* || true"

# cp -a ./* doesn't copy dotfiles; use rsync if available, else cp -a ./. (includes dotfiles)
if command -v rsync >/dev/null 2>&1; then
  sudo rsync -a --delete ./ "${RELEASES_DIR}/${TAG}/"
else
  sudo cp -a ./. "${RELEASES_DIR}/${TAG}/"
fi

log "Switch current symlink..."
sudo ln -sfn "${RELEASES_DIR}/${TAG}" "${CURRENT_DIR}"

# render env atomically and fail deploy if empty/missing
log "Render .env from Parameter Store path: ${SSM_PATH}"
ENV_TMP="/tmp/${APP_NAME}.env.${TAG}.$RANDOM"

cleanup() {
  sudo rm -f "${ENV_TMP}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

aws ssm get-parameters-by-path \
  --path "${SSM_PATH}" \
  --recursive \
  --with-decryption \
  --query "Parameters[*].[Name,Value]" \
  --output text \
| awk -F'\t' '{
    name=$1; sub(".*/","",name);
    # systemd EnvironmentFile expects valid shell-ish var names
    if (name !~ /^[A-Za-z_][A-Za-z0-9_]*$/) {
      print "Invalid env var name from SSM: " name > "/dev/stderr";
      exit 3;
    }
    print name"="$2
  }' \
| sudo tee "${ENV_TMP}" >/dev/null

sudo test -s "${ENV_TMP}"
sudo mv "${ENV_TMP}" "${ENV_FILE}"
sudo chmod 600 "${ENV_FILE}"
log "OK: rendered env keys count: $(sudo wc -l < "${ENV_FILE}")"

# write runtime env (image uri) for systemd unit expansion
{
  echo "ATTA_IMAGE=${ATTA_IMAGE}"
  echo "ATTA_TAG=${TAG}"
} | sudo tee "${RUNTIME_ENV_FILE}" >/dev/null
sudo chmod 600 "${RUNTIME_ENV_FILE}"

# docker login to ECR and pull image (uses instance role)
ECR_REGISTRY="$(echo "${ATTA_IMAGE}" | awk -F/ '{print $1}')"

log "Login to ECR: ${ECR_REGISTRY} (region=${AWS_REGION})"

# capture login password generation error clearly
LOGIN_PASSWORD="$(aws ecr get-login-password --region "${AWS_REGION}")"
sudo docker login --username AWS --password-stdin "${ECR_REGISTRY}" <<< "${LOGIN_PASSWORD}"

# disk-space guard with auto-recovery attempt (safe-by-default: no volume prune)
FREE_KB="$(df --output=avail -k / | tail -1 | tr -d ' ')"
if (( FREE_KB < 1 * 1024 * 1024 )); then
  log "WARN: Low disk space on /. Attempting Docker cleanup (images/build cache only)..."
  sudo docker image prune -af >/dev/null 2>&1 || true
  sudo docker builder prune -af >/dev/null 2>&1 || true

  # Optional: prune volumes only if explicitly allowed (volumes may contain data)
  if [[ "${ALLOW_DOCKER_PRUNE_VOLUMES:-0}" == "1" ]]; then
    log "WARN: ALLOW_DOCKER_PRUNE_VOLUMES=1 set, pruning volumes too..."
    sudo docker system prune --volumes --force >/dev/null 2>&1 || true
  fi

  FREE_KB="$(df --output=avail -k / | tail -1 | tr -d ' ')"
fi

# fail if less than 1GB free on /
if (( FREE_KB < 1 * 1024 * 1024 )); then
  log "ERROR: Not enough free disk space on /. Need >= 1GB free."
  df -h / 2>&1 | sudo tee -a "${LOG_FILE}" >&2 || true
  exit 1
fi

log "Pull image: ${ATTA_IMAGE}"
sudo docker pull "${ATTA_IMAGE}"

log "Install systemd unit..."
sudo cp "${CURRENT_DIR}/deploy/systemd/atta.service" /etc/systemd/system/atta.service
sudo test -f /etc/systemd/system/atta.service

# normalize CRLF -> LF to avoid "Invalid argument"
sudo sed -i 's/\r$//' /etc/systemd/system/atta.service

# validate the unit file now (gives exact error line if broken)
# persist verify output to log file for later debugging
log "Validate systemd unit (systemd-analyze verify)..."
if ! sudo systemd-analyze verify /etc/systemd/system/atta.service 2>&1 | sudo tee -a "${LOG_FILE}" >/dev/null; then
  die "systemd-analyze verify failed. See ${LOG_FILE}."
fi

sudo systemctl daemon-reload

# enable unit on boot
sudo systemctl enable atta.service

log "Start (or restart) atta.service..."
if ! sudo systemctl restart atta.service; then
  log "ERROR: failed to restart atta.service"
  dump_service_logs
  exit 1
fi

sleep 1

# check if the service to be active
if ! sudo systemctl is-active --quiet atta.service; then
  log "ERROR: atta.service is not active. Recent logs:"
  dump_service_logs
  exit 1
fi

# ensure the expected container is actually running
if ! sudo docker ps --format '{{.Names}}' | grep -qx "atta"; then
  log "ERROR: docker container 'atta' is not running."
  sudo docker ps -a 2>&1 | sudo tee -a "${LOG_FILE}" >&2 || true
  dump_service_logs
  exit 1
fi

log "Done. Docker image pulled, unit installed, service restarted."
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

sudo mkdir -p "${RELEASES_DIR}/${TAG}" "${STATE_DIR}/output"

command -v aws >/dev/null 2>&1 || { echo "AWS CLI missing on EC2" >&2; exit 1; }

# install docker on EC2 if missing
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker missing. Installing..."
  sudo dnf install -y docker
fi

echo "Enable & start docker..."
sudo systemctl enable --now docker

echo "Copy deploy bundle to releases..."
# persist the extracted deploy bundle to /opt/atta/releases/<TAG>

# rm -rf dir/* doesn't remove dotfiles, so wipe them too
sudo bash -c "rm -rf '${RELEASES_DIR:?}/${TAG:?}/'* '${RELEASES_DIR:?}/${TAG:?}/'.[!.]* '${RELEASES_DIR:?}/${TAG:?}/'..?* || true"

# cp -a ./* doesn't copy dotfiles; use rsync if available, else cp -a ./. (includes dotfiles)
if command -v rsync >/dev/null 2>&1; then
  sudo rsync -a --delete ./ "${RELEASES_DIR}/${TAG}/"
else
  sudo cp -a ./. "${RELEASES_DIR}/${TAG}/"
fi

echo "Switch current symlink..."
sudo ln -sfn "${RELEASES_DIR}/${TAG}" "${CURRENT_DIR}"

# render env atomically and fail deploy if empty/missing
echo "Render .env from Parameter Store path: ${SSM_PATH}"
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
echo "OK: rendered env keys count: $(sudo wc -l < "${ENV_FILE}")"

# write runtime env (image uri) for systemd unit expansion
{
  echo "ATTA_IMAGE=${ATTA_IMAGE}"
  echo "ATTA_TAG=${TAG}"
} | sudo tee "${RUNTIME_ENV_FILE}" >/dev/null
sudo chmod 600 "${RUNTIME_ENV_FILE}"

# docker login to ECR and pull image (uses instance role)
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_REGION
export AWS_DEFAULT_REGION="${AWS_REGION}"

ECR_REGISTRY="$(echo "${ATTA_IMAGE}" | awk -F/ '{print $1}')"

echo "Login to ECR: ${ECR_REGISTRY}"

# capture login password generation error clearly
LOGIN_PASSWORD="$(aws ecr get-login-password --region "${AWS_REGION}")"
sudo docker login --username AWS --password-stdin "${ECR_REGISTRY}" <<< "${LOGIN_PASSWORD}"

# fail if less than 1GB free on /
FREE_KB="$(df --output=avail -k / | tail -1 | tr -d ' ')"
if (( FREE_KB < 1 * 1024 * 1024 )); then
  echo "ERROR: Not enough free disk space on /. Need >= 1GB free." >&2
  df -h /
  exit 1
fi

echo "Pull image: ${ATTA_IMAGE}"
sudo docker pull "${ATTA_IMAGE}"

echo "Install systemd unit..."
sudo cp "${CURRENT_DIR}/deploy/systemd/atta.service" /etc/systemd/system/atta.service
sudo test -f /etc/systemd/system/atta.service

# normalize CRLF -> LF to avoid "Invalid argument"
sudo sed -i 's/\r$//' /etc/systemd/system/atta.service

# validate the unit file now (gives exact error line if broken)
sudo systemd-analyze verify /etc/systemd/system/atta.service

sudo systemctl daemon-reload

# enable unit on boot
sudo systemctl enable atta.service

echo "Start (or restart) atta.service..."
if ! sudo systemctl restart atta.service; then
  echo "ERROR: failed to restart atta.service" >&2
  sudo systemctl status atta.service --no-pager -l >&2 || true
  sudo journalctl -u atta.service -n 200 --no-pager >&2 || true
  exit 1
fi

sleep 1

# check if the service to be active
if ! sudo systemctl is-active --quiet atta.service; then
  echo "ERROR: atta.service is not active. Recent logs:" >&2
  sudo systemctl status atta.service --no-pager -l >&2 || true
  sudo journalctl -u atta.service -n 200 --no-pager >&2 || true
  exit 1
fi

# ensure the expected container is actually running
if ! sudo docker ps --format '{{.Names}}' | grep -qx "atta"; then
  echo "ERROR: docker container 'atta' is not running." >&2
  sudo docker ps -a >&2 || true
  sudo systemctl status atta.service --no-pager -l >&2 || true
  sudo journalctl -u atta.service -n 200 --no-pager >&2 || true
  exit 1
fi

echo "Done. Docker image pulled, unit installed, service restarted."
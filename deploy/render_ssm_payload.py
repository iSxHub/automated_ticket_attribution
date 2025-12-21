#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex


def _q(value: str) -> str:
    return shlex.quote(value)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tag", required=True)
    p.add_argument("--aws-region", required=True)
    p.add_argument("--atta-image", required=True)
    p.add_argument("--bucket", required=True)
    p.add_argument("--ssm-path", required=True)
    args = p.parse_args()

    commands = [
        "set -euo pipefail",
        f"export TAG={_q(args.tag)}",
        f"export ATTA_IMAGE={_q(args.atta_image)}",
        f"export SSM_PATH={_q(args.ssm_path)}",
        f"export DEPLOY_BUCKET={_q(args.bucket)}",
        f"export AWS_REGION={_q(args.aws_region)}",
        'echo "[SSM] whoami=$(whoami)"',
        'echo "[SSM] TAG=${TAG}"',
        'echo "[SSM] ATTA_IMAGE=${ATTA_IMAGE}"',
        'echo "[SSM] SSM_PATH=${SSM_PATH}"',
        'echo "[SSM] AWS_REGION=${AWS_REGION}"',
        'bundle="atta-${TAG}.tar.gz"',
        'bundle_sha="${bundle}.sha256"',
        's3_uri="s3://${DEPLOY_BUCKET}/atta/${TAG}/${bundle}"',
        's3_sha_uri="s3://${DEPLOY_BUCKET}/atta/${TAG}/${bundle_sha}"',
        'echo "[SSM] Download bundle: ${s3_uri}"',
        'echo "[SSM] Download checksum: ${s3_sha_uri}"',
        'WORK_DIR="/tmp/atta-deploy-${TAG}-$RANDOM"',
        'mkdir -p "${WORK_DIR}"',
        'cd "${WORK_DIR}"',
        'aws --region "${AWS_REGION}" s3 cp "${s3_uri}" "${bundle}"',
        'aws --region "${AWS_REGION}" s3 cp "${s3_sha_uri}" "${bundle_sha}"',
        # verify checksum BEFORE extract
        'command -v sha256sum >/dev/null 2>&1 || { echo "[SSM] ERROR: sha256sum missing" >&2; exit 3; }',
        'echo "[SSM] Verify checksum..."',
        'sha256sum -c "${bundle_sha}"',
        'echo "[SSM] Checksum OK"',
        "tar -xzf \"${bundle}\"",
        "chmod +x deploy/ec2_deploy.sh",
        # pass explicit args (single source of truth)
        './deploy/ec2_deploy.sh '
        '--aws-region "${AWS_REGION}" '
        '--tag "${TAG}" '
        '--atta-image "${ATTA_IMAGE}" '
        '--ssm-path "${SSM_PATH}"',
    ]

    print(json.dumps({"commands": commands}))


if __name__ == "__main__":
    main()
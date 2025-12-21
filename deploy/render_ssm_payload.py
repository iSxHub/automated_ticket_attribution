#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tag", required=True)
    p.add_argument("--aws-region", required=True)
    p.add_argument("--atta-image", required=True)
    p.add_argument("--bucket", required=True)
    p.add_argument("--ssm-path", required=True)
    args = p.parse_args()

    s3_uri = f"s3://{args.bucket}/atta/{args.tag}/atta-{args.tag}.tar.gz"

    commands = [
        "set -euo pipefail",
        f"export TAG='{args.tag}'",
        f"export AWS_REGION='{args.aws_region}'",
        f"export AWS_DEFAULT_REGION='{args.aws_region}'",
        f"export ATTA_IMAGE='{args.atta_image}'",
        f"export SSM_PATH='{args.ssm_path}'",
        "echo '[SSM] whoami='$(whoami)",
        "echo '[SSM] TAG='${TAG}",
        "echo '[SSM] ATTA_IMAGE='${ATTA_IMAGE}",
        "echo '[SSM] SSM_PATH='${SSM_PATH}'",
        f"echo '[SSM] Download bundle: {s3_uri}'",
        "WORK_DIR=\"/tmp/atta-deploy-${TAG}-$RANDOM\"",
        "mkdir -p \"$WORK_DIR\"",
        "cd \"$WORK_DIR\"",
        f"aws s3 cp '{s3_uri}' bundle.tar.gz",
        "tar -xzf bundle.tar.gz",
        "chmod +x deploy/ec2_deploy.sh",
        "./deploy/ec2_deploy.sh",
    ]

    print(json.dumps({"commands": commands}))


if __name__ == "__main__":
    main()
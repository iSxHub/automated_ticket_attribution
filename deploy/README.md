# Automated Ticket Attribution (ATTA) deploy (dev)

## Tag convention
Deploy workflow triggers on tags matching: `*-dev`
Example: `0.1.23-dev`

## End-to-end flow
1. CI runs on PRs and pushes to `dev`/`main`.
2. When you create and push a `*-dev` tag:
   - GitHub Actions builds + pushes the Docker image to ECR
   - Packs the repo into a deploy bundle `atta-<tag>.tar.gz`
   - Uploads the bundle to S3: `s3://<DEPLOY_BUCKET>/atta/<tag>/atta-<tag>.tar.gz`
3. GitHub Actions sends an AWS SSM Run Command to the AWS EC2 instance:
   - Downloads the bundle from S3
   - Runs `deploy/ec2_deploy.sh` on the instance
4. EC2 deploy script:
   - Writes `/opt/atta/.env` from AWS SSM Parameter Store path (e.g. `/atta/dev`)
   - Writes `/opt/atta/state/runtime.env` containing `ATTA_IMAGE` and `ATTA_TAG`
   - Pulls the Docker image from AWS ECR
   - Installs/validates systemd unit and restarts `atta.service`

## Debugging
- Deploy log on the instance: `/var/log/atta-deploy.log`
- Service logs:
  - `sudo systemctl status atta.service -l --no-pager`
  - `sudo journalctl -u atta.service -n 200 --no-pager`
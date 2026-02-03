# Deployment Workflow

## Overview

The `make deploy-dev` command orchestrates an automated deployment pipeline that follows clean architecture principles and leverages GitHub Actions, AWS ECR, S3, EC2, and SSM for continuous delivery to the development environment.

---

## Architecture Diagram

```
┌──────────────┐
│   Developer  │
└──────┬───────┘
       │ make deploy-dev
       ▼
┌──────────────────────────────────────────────────────────┐
│  Local Git Operations (Makefile)                         │
│  1. Fetch tags                                           │
│  2. Branch validation (must be 'dev')                    │
│  3. Version tagging (e.g., 0.1.30-dev)                   │
│  4. Push branch & tags                                   │
└──────────────┬───────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────┐
│  GitHub Actions (.github/workflows/deploy-dev.yml)       │
│  Trigger: on push of tags matching '*-dev'               │
└──────────────┬───────────────────────────────────────────┘
               │
       ┌───────┴────────┬──────────────┐
       ▼                ▼              ▼
┌──────────┐     ┌──────────┐   ┌──────────┐
│   Build  │     │  Upload  │   │  Deploy  │
│  Docker  │────▶│  Bundle  │──▶│  to EC2  │
│  to ECR  │     │  to S3   │   │ via SSM  │
└──────────┘     └──────────┘   └──────────┘
                                       │
                                       ▼
                                ┌──────────────┐
                                │  EC2 Instance│
                                │  (systemd)   │
                                └──────────────┘
```

---

## Detailed Workflow

### Phase 1: Local Development (Make Target)

#### Command
```bash
make deploy-dev
```

#### Steps

**1.1 Fetch Remote Tags**
```bash
git fetch --tags
```
Ensures local Git has the latest tags from remote, preventing version conflicts.

**1.2 Branch Validation**
```bash
branch=$(git branch --show-current)
if [ "$branch" != "dev" ]; then
    echo "Error: Can only deploy-dev from dev branch"
    exit 1
fi
```
**Purpose:** Enforces deployment hygiene by restricting dev deployments to the `dev` branch only.

**1.3 Version Tagging** (via `make tag SUFFIX=dev`)

```bash
# Shows last 5 dev tags
git tag -l "[0-9]*.[0-9]*.[0-9]*-dev" --sort=-version:refname | head -5

# Calculates next version (auto-increments patch number)
# Example: 0.1.29-dev → 0.1.30-dev

# Prompts developer for version (with calculated default)
echo -n "Enter new version (leave blank for default: $next_version): "
read version

# Validates version ends with '-dev'
if ! echo "$version" | grep -q "\-dev$"; then
    echo "Error: Version must end with -dev"
    exit 1
fi

# Creates git tag
git tag $version && echo "Tagged: $version"
```

**Version Format:** `MAJOR.MINOR.PATCH-SUFFIX`
- Example: `0.1.30-dev`
- Suffix must be `-dev` for development deployments

**1.4 Push to Remote**
```bash
git push origin dev      # Push branch commits
git push --tags         # Push newly created tag
```

---

### Phase 2: GitHub Actions CI/CD

#### Trigger
```yaml
on:
  push:
    tags:
      - '*-dev'  # Matches any tag ending with '-dev'
```

The pushed tag (e.g., `0.1.30-dev`) automatically triggers the deployment workflow.

#### Job 1: Build & Push Docker Image to ECR

**Prerequisites:**
- AWS credentials configured in GitHub Secrets
- ECR repository created: `{AWS_ACCOUNT_ID}.dkr.ecr.{REGION}.amazonaws.com/{REPO_NAME}`

**Steps:**

1. **Checkout Code**
   ```yaml
   - uses: actions/checkout@v4
   ```

2. **Configure AWS Credentials**
   ```yaml
   - uses: aws-actions/configure-aws-credentials@v4
     with:
       aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
       aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
       aws-region: ${{ secrets.AWS_REGION }}
   ```

3. **Login to Amazon ECR**
   ```yaml
   - uses: aws-actions/amazon-ecr-login@v2
   ```

4. **Build Docker Image**
   ```bash
   docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
   ```
   - `IMAGE_TAG` is extracted from the git tag (e.g., `0.1.30-dev`)
   - Also tagged as `latest-dev` for easy rollback reference

5. **Push to ECR**
   ```bash
   docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
   docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest-dev
   ```

---

#### Job 2: Create & Upload Deploy Bundle to S3

**Purpose:** Package deployment scripts and configuration for EC2 consumption.

**Bundle Contents:**
```
deploy-bundle-{VERSION}.tar.gz
├── deploy/
│   ├── ec2_deploy.sh           # Main deployment orchestrator
│   ├── systemd/
│   │   └── atta.service        # systemd service definition
│   └── .env.example            # Environment template
└── VERSION                     # Version identifier file
```

**Steps:**

1. **Build Bundle**
   ```bash
   ./deploy/build_bundle.sh $TAG_VERSION
   ```
   Creates `deploy-bundle-{VERSION}.tar.gz` with deployment artifacts.

2. **Upload to S3**
   ```bash
   aws s3 cp deploy-bundle-$VERSION.tar.gz \
     s3://$DEPLOY_BUCKET/bundles/dev/
   ```

**S3 Structure:**
```
s3://{DEPLOY_BUCKET}/
└── bundles/
    └── dev/
        ├── deploy-bundle-0.1.30-dev.tar.gz
        ├── deploy-bundle-0.1.29-dev.tar.gz
        └── ...
```

---

#### Job 3: Deploy to EC2 via AWS Systems Manager (SSM)

**Architecture Benefits:**
- ✅ No need to open SSH ports (port 22)
- ✅ No SSH key management
- ✅ Centralized logging via CloudWatch
- ✅ IAM-based access control
- ✅ Session audit trail

**Prerequisites:**
- EC2 instance has SSM Agent installed and running
- EC2 instance has IAM role with SSM permissions
- EC2 instance tagged appropriately for targeting

**Steps:**

1. **Download Deploy Bundle from S3**
   ```bash
   aws ssm send-command \
     --instance-ids $INSTANCE_ID \
     --document-name "AWS-RunShellScript" \
     --parameters commands=[
       "cd /opt/atta",
       "aws s3 cp s3://$BUCKET/bundles/dev/deploy-bundle-$VERSION.tar.gz .",
       "tar -xzf deploy-bundle-$VERSION.tar.gz"
     ]
   ```

2. **Execute Deployment Script**
   ```bash
   aws ssm send-command \
     --instance-ids $INSTANCE_ID \
     --document-name "AWS-RunShellScript" \
     --parameters commands=[
       "cd /opt/atta",
       "./deploy/ec2_deploy.sh $VERSION $IMAGE_TAG"
     ]
   ```

3. **Deployment Script Actions** (`ec2_deploy.sh`):

   a. **Pull Docker Image**
   ```bash
   aws ecr get-login-password --region $REGION | \
     docker login --username AWS --password-stdin $ECR_REGISTRY
   
   docker pull $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
   ```

   b. **Stop Existing Service**
   ```bash
   systemctl stop atta.service
   ```

   c. **Update systemd Service**
   ```bash
   cp deploy/systemd/atta.service /etc/systemd/system/
   systemctl daemon-reload
   ```

   d. **Start New Version**
   ```bash
   systemctl start atta.service
   systemctl enable atta.service  # Enable auto-start on boot
   ```

   e. **Health Check**
   ```bash
   systemctl status atta.service
   docker ps | grep atta
   ```

---

### Phase 3: Service Runtime (systemd on EC2)

#### systemd Unit File Structure

**Location:** `/etc/systemd/system/atta.service`

```ini
[Unit]
Description=Automated Ticket Attribution Service
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=no
WorkingDirectory=/opt/atta
EnvironmentFile=/opt/atta/.env

# Pull latest image and run container
ExecStartPre=/usr/bin/docker pull ${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}
ExecStart=/usr/bin/docker run --rm \
  --name atta \
  --env-file /opt/atta/.env \
  -v /opt/atta/output:/app/output \
  ${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}

# Cleanup
ExecStop=/usr/bin/docker stop atta
ExecStopPost=/usr/bin/docker rm -f atta

Restart=no
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Key Configuration:**
- **Type=oneshot:** Service runs once and exits (not a daemon)
- **Volume Mount:** Persists generated reports to host filesystem
- **Environment:** Loads secrets and config from `/opt/atta/.env`
- **Logging:** All output goes to systemd journal (viewable via `journalctl`)

---

## Clean Architecture Alignment

### Separation of Concerns

| Layer | Responsibility | Components |
|-------|---------------|------------|
| **Entrypoint** | Deployment orchestration | Makefile targets |
| **Application** | CI/CD workflow logic | GitHub Actions workflows |
| **Infrastructure** | Cloud services integration | ECR, S3, SSM, EC2 |
| **Domain** | Service runtime behavior | Docker container + systemd |

### Dependency Direction

```
Makefile (local) ──▶ GitHub Actions ──▶ AWS Services ──▶ EC2 Runtime
     │                     │                  │              │
     │                     │                  │              ▼
     └─────────────────────┴──────────────────┴──── Service Execution
                  (Dependencies point inward)
```

### Benefits

1. **Single Responsibility:** Each phase has one clear purpose
2. **Loose Coupling:** Phases communicate through well-defined interfaces (Git tags, S3 bundles, SSM commands)
3. **Easy Testing:** Each component can be tested independently
4. **Replaceability:** Any phase can be replaced without affecting others (e.g., swap ECR for Docker Hub)

---

## Environment Configuration

### Required AWS Resources

| Resource | Purpose | Example |
|----------|---------|---------|
| **ECR Repository** | Store Docker images | `123456789.dkr.ecr.us-east-1.amazonaws.com/atta` |
| **S3 Bucket** | Store deploy bundles | `s3://atta-deploy-artifacts` |
| **EC2 Instance** | Run service | `i-0abc123def456789` |
| **IAM Role (EC2)** | SSM + ECR + S3 access | `atta-ec2-role` |
| **SSM Agent** | Remote command execution | Pre-installed on Amazon Linux 2 |

### Required GitHub Secrets

```
AWS_ACCESS_KEY_ID          # For GitHub Actions AWS access
AWS_SECRET_ACCESS_KEY      # For GitHub Actions AWS access
AWS_REGION                 # e.g., us-east-1
ECR_REGISTRY               # e.g., 123456789.dkr.ecr.us-east-1.amazonaws.com
ECR_REPOSITORY             # e.g., atta
DEPLOY_BUCKET              # e.g., atta-deploy-artifacts
EC2_INSTANCE_ID            # e.g., i-0abc123def456789
```

---

## Deployment Flow Example

### Complete Deployment Timeline

```
T+0s    Developer: make deploy-dev
T+5s    Local: Creates tag 0.1.30-dev
T+10s   Local: Pushes tag to GitHub
T+15s   GitHub: Workflow triggered
T+30s   GitHub: Docker build starts
T+2m    GitHub: Image pushed to ECR
T+2m10s GitHub: Bundle uploaded to S3
T+2m20s GitHub: SSM command sent to EC2
T+2m30s EC2: Downloads bundle from S3
T+2m40s EC2: Pulls Docker image from ECR
T+2m50s EC2: Stops old service
T+3m    EC2: Starts new service
T+3m10s EC2: Health check passes
T+3m15s GitHub: Deployment marked successful
```

---

## Rollback Procedure

### Quick Rollback (Same Session)

```bash
# 1. Find previous version tag
git tag -l "*-dev" --sort=-version:refname | head -5

# 2. Re-push previous tag with force (triggers re-deployment)
git push origin refs/tags/0.1.29-dev:refs/tags/0.1.29-dev --force
```

### Manual Rollback on EC2

```bash
# SSH into EC2 (or use SSM Session Manager)
aws ssm start-session --target $INSTANCE_ID

# Pull previous version
docker pull $ECR_REGISTRY/$ECR_REPOSITORY:0.1.29-dev

# Update environment to use old version
sed -i 's/IMAGE_TAG=.*/IMAGE_TAG=0.1.29-dev/' /opt/atta/.env

# Restart service
systemctl restart atta.service

# Verify
systemctl status atta.service
docker ps | grep atta
```

---

## Monitoring & Troubleshooting

### View Deployment Logs

**GitHub Actions:**
```
Repository → Actions → deploy-dev workflow → Recent run
```

**EC2 Service Logs:**
```bash
# Via SSM
aws ssm start-session --target $INSTANCE_ID

# systemd journal
journalctl -u atta.service -f

# Docker logs
docker logs -f atta
```

## Quick Reference

### Commands

```bash
# Development workflow
make deploy-dev              # Full deployment
make tag SUFFIX=dev         # Just create tag (no push)
git push --delete origin TAG # Delete remote tag

# AWS operations (from local machine)
aws ecr describe-images --repository-name atta --region us-east-1
aws s3 ls s3://atta-deploy-artifacts/bundles/dev/
aws ssm start-session --target $INSTANCE_ID

# EC2 operations (via SSM session)
systemctl status atta.service
systemctl restart atta.service
journalctl -u atta.service --since "10 minutes ago"
docker ps -a | grep atta
docker logs atta
```

### File Locations

| Component | Path |
|-----------|------|
| Makefile | `./Makefile` |
| Deployment scripts | `./deploy/` |
| systemd unit | `./deploy/systemd/atta.service` |
| GitHub workflow | `./.github/workflows/deploy-dev.yml` |
| EC2 service dir | `/opt/atta/` |
| EC2 environment | `/opt/atta/.env` |
| EC2 systemd unit | `/etc/systemd/system/atta.service` |
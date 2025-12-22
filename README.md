# Automated Ticket Attribution

Project implements a small automation pipeline that simulates
automatic classification of IT helpdesk tickets based on an IT Service Catalog.

## Features / Pipeline overview

### Task
1. Fetch helpdesk requests from the webhook endpoint using API key + secret.
2. Fetch the Service Catalog (YAML) from a remote URL.
3. Batch requests to the LLM (configurable batch size, default 30).
4. Let the LLM fill `request_category`, `request_type`, `sla_unit`, `sla_value` based on the Service Catalog.
5. Generate a sorted Excel report with formatting.
6. Send the report via SMTP to the configured recipient, including a link to the codebase.

### Additional features
- Deploy dev: GitHub Actions workflow triggered by *-dev tags builds/pushes a Docker image to ECR, uploads a deploy bundle to S3, and deploys to the dev EC2 instance via SSM + systemd.
- Idempotent report sending: scan `output/*.xlsx`, send any report not marked as sent in SQLite (oldest-first by mtime), and only then run the Helpdesk API + LLM pipeline.
- Log all key steps via Python `logging` and provide a simple terminal progress indicator (spinner).
- Covered by unit and integration tests and static checks (ruff, mypy).
- Helpdesk API and Service Catalog HTTP calls have retry + exponential backoff (configurable `max_retries`, `backoff_factor`).
- Supports sending multiple attachments in one email (all pending reports in a single message).
- Supports an explicit report path mode (send a specific report if it isn’t logged as sent yet).
- LLM output is strictly validated (must be JSON, must contain `items`, items must be dicts and include `id`), otherwise the batch is treated as failed.
- If an LLM batch fails, requests from that batch are still included “as-is” in the Excel report (degradation strategy instead of hard failing).
- LLM-provided SLA fields are explicitly ignored (warned in logs). SLA is derived from the Service Catalog only.
- Added ServiceCatalogMatcher that normalizes/canonicalizes `(request_category, request_type)` coming from the LLM:
  - case-insensitive + whitespace-normalized matching
  - rejects non-catalog pairs
  - protects against normalization collisions (ambiguous matches)
- Centralized env-based config loading (via `python-dotenv`) with required-variable checks + defaults:
  - LLM tuning: `LLM_BATCH_SIZE`, `LLM_DELAY_BETWEEN_BATCHES`, `LLM_TEMPERATURE`, `LLM_TOP_P`, `LLM_TOP_K`
  - report log DB path, SMTP TLS flag, etc.
- Email body is generated from packaged templates (text + HTML), with HTML escaping for safety.
- SMTP sender validates attachments exist, logs total attachment size, supports TLS (`starttls`) toggle.

---
## Assumptions and open questions based on the task

This project makes a few pragmatic assumptions about the Service Catalog and LLM behavior.
For a detailed discussion (including Jira vs Zoom classification, idempotency, error handling,
and security considerations), see [`DESIGN_NOTES.md`](DESIGN_NOTES.md).

In short:

- `SaaS Platform Access (Jira/Salesforce)` is treated as specific to Jira and Salesforce,
  not as a generic bucket for all SaaS tools.
- Jira/Salesforce incidents (including outages like "Jira is down") are mapped to
  `Software & Licensing / SaaS Platform Access (Jira/Salesforce)` with the catalog SLA (8 hours).
- Zoom is not present in the Service Catalog. For the "Zoom not working" request, the long
  description says "Camera isn't detected in Zoom". I treat this as an endpoint/device/configuration
  issue (camera/drivers/permissions) rather than a SaaS availability or access problem, so it is
  classified as `Software & Licensing / Other Software Issue` with SLA 24 hours.
---
## Potential future improvements

- Package the pipeline into a Docker container and run it on a schedule (cron / n8n).
- Cache Service Catalog fetch (etag/if-modified-since) to reduce network and speed up runs.
- Move all configuration (URLs, keys, batch sizes, email recipients, etc) into environment-based settings per environment (dev/stage/prod) (n8n).
- Write logs to a file (log rotation), not only stdout. Logs in JSON.
- Add an alert message with short success/failure + key metrics to, for example, a Telegram alerts channel (n8n).
- Extend the SQLite report log table to store `sender` and `recipient` columns.
- Store generated reports on the host (or in cloud storage), with download support (n8n).
- Add Telegram commands (as an example for any chat platform) (n8n):
  - run the pipeline once on demand,
  - configure the n8n schedule,
  - request the “sent reports” table as a file export,
  - download a previously sent report (from host storage or cloud),
  - request recent logs.
- If service became always running one, add Prometheus metrics + Grafana dashboards:
  - service health (up/down),
  - number of reports sent per day,
  - recipients distribution per day.
---
## Tech Stack

- Python 3.10
- Google Gemini 2.5 Pro (LLM for classification)
- Clean Architecture (domain / application / infrastructure / entrypoint)

---
## Structure

```text
automated_ticket_attribution/
  app/
    cmd/
        main.py             # run app
    domain/                 # models
    infrastructure/         # integrations
    application/            # use-cases
    shared/
    config.py
  tests/
  output/
  requirements.txt
  requirements-dev.txt
  LICENSE
  Makefile
  README.md
```
---
## Setup

### prod
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
### dev
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```
### local .env
```text
rename env_local.example to .env and fill the values
```
--- 
## How to Run

From the project root:

```bash
make run        # run the app
make test       # run unit tests (pytest)
make lint       # lint with ruff
make type-check # static type checking with mypy
make excel      # build example excel file
```
---
## How to deploy on AWS EC2
### Make this files executable locally (optional, for local debugging):
```text
chmod +x deploy/ec2_deploy.sh
chmod +x deploy/build_bundle.sh
chmod +x deploy/ssm_deploy.sh
```
### Deploy dev (GitHub Actions)
make deploy-dev creates and pushes a *-dev tag (for example: 0.1.30-dev).
That tag triggers the deploy-dev workflow: build/push image to ECR, upload bundle to S3, then deploy to EC2 via SSM + systemd.
```text
make deploy-dev
```
More info about Deploy [`deploy/README.md`](deploy/README.md)
## License

Source-available, non-commercial.  
You can read and run this code for evaluation, but you may not use it in production
or for commercial purposes without my written permission.
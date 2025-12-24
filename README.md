# Automated Ticket Attribution

Automated pipeline that matches and classifies IT helpdesk tickets against an IT Service Catalog using an LLM, then generates and emails a report.

**Architecture:** Clean Architecture (Domain / Application / Infrastructure / Entrypoint).

---
## 🧩 Features / Pipeline overview

### Task
1. Fetch helpdesk requests from the webhook endpoint using API key + secret.
2. Fetch the Service Catalog (YAML) from a remote URL.
3. Batch requests to the LLM (configurable batch size, default 30).
4. Let the LLM fill `request_category`, `request_type`, `sla_unit`, `sla_value` based on the Service Catalog.
5. Generate a sorted Excel report with formatting.
6. Send the report via SMTP to the configured recipient, including a link to the codebase.

### Additional features
- Deploy dev: GitHub Actions workflow triggered by *-dev tags builds/pushes a Docker image to ECR, uploads a deploy bundle to S3, and deploys to the dev EC2 instance via SSM + systemd.
- Manual run via self-hosted n8n on the EC2: a workflow runs the pipeline on demand through SSH, prevents double-runs with `flock`, streams logs to n8n, and persists them to `/var/log/atta-manual-run.log` (with a “tail last logs” step).
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
## ❓ Assumptions and open questions based on the task

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
## 🛣️ Potential future improvements

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
## 🚀 Quick start

### Requirements
- Python 3.10+
- `make`

### Setup and run

```bash
# 1) Create and activate venv
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2) Install deps
# 2.1) Dev (recommended for local work)
pip install -r requirements-dev.txt
# 2.2) Prod (runtime only)
pip install -r requirements.txt

# 3) Create local .env
cp env_local.example .env  # Windows: copy env_local.example .env

# 4) Run
make run
````
Open `.env` and fill required values before running.

---
## 📁 Structure

```text
automated_ticket_attribution/
├── app/                  # Application source code
│   ├── domain/           # Domain layer (pure business models/rules)
│   ├── application/      # Use-cases + ports (interfaces)
│   │   ├── dto/          # Use-case DTOs
│   │   └── ports/        # Ports (interfaces) for infra adapters
│   ├── infrastructure/   # Adapters/clients (HTTP/LLM/Excel/SMTP/config/etc.)
│   │   └── email_templates/ # Email templates + builders
│   ├── shared/           # Shared utilities (exceptions/helpers)
│   └── cmd/              # Entrypoints (CLI wiring + pipeline runner)
│
├── tests/                # Automated tests
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
│
├── deploy/               # Deployment tooling (AWS EC2 / SSM)
│   └── systemd/          # systemd unit files
│
├── .github/              # CI/CD
│   ├── actions/          # Composite actions
│   └── workflows/        # GitHub Actions workflows
│
└── output/               # Generated artifacts (reports, db, etc.)
```
---

## 🛠️ Useful commands

```bash
make test        # run tests (pytest)
make lint        # lint (ruff)
make type-check  # type checking (mypy)
make excel       # generate example Excel output
```
---

## 🏗️ Base pipeline pattern

The project follows **Clean Architecture** and runs as a single **CLI pipeline**.

- **Ports (contracts):** `app/application/ports/`, `app/cmd/ports.py`
- **Use-cases:** `app/application/`
- **Adapters (I/O):** `app/infrastructure/`
- **Entrypoint:** `app/cmd/main.py`
- **Wiring / runner:** `app/cmd/pipeline.py` → `app/cmd/pipeline_service.py`

**Flow:** send unsent reports → else fetch tickets → load Service Catalog → LLM classify → enrich SLA → export Excel → email report → log status (SQLite).

---
## ☁️ Dev deployment (GitHub Actions to EC2 via SSM)

### Make deploy scripts executable (optional, only for running locally)
```bash
chmod +x deploy/ec2_deploy.sh
chmod +x deploy/build_bundle.sh
chmod +x deploy/ssm_deploy.sh
````

### Deploy dev (GitHub Actions)

`make deploy-dev` creates and pushes a `*-dev` tag (for example: `0.1.30-dev`).

That tag triggers the `deploy-dev` workflow:

* build and push the Docker image to **ECR**
* upload the deploy bundle to **S3**
* deploy to the dev **EC2** instance via **SSM** + **systemd**

```bash
make deploy-dev
```

More details: [`deploy/README.md`](deploy/README.md)

---
## ▶️ Manual run via n8n (self-hosted on EC2)

The workflow triggers the pipeline inside the already-running `atta` Docker container via `docker exec`.

### Connect to n8n UI from your local machine (SSH tunnel)

n8n is bound to localhost (`127.0.0.1:5678`) and is not exposed publicly.

On local machine:
```bash
ssh -i path_to_ssh_key -L 5678:127.0.0.1:5678 root@<EC2_PUBLIC_IP>
```

Open in web browser:
```bash
http://localhost:5678
```

**Workflow: “atta service (start)”**

Nodes:

1) Manual Trigger
2) SSH → Execute Command (container status check)
3) SSH → Execute Command (run pipeline + prevent double runs + persist logs)
4) SSH → Execute Command (show last logs)

Note: nodes 2–4 run on the EC2 host using SSH credentials configured in n8n.

---
## 🧰 Tech stack

- **Language:** Python 3.10+
- **LLM:** Gemini via Google GenAI SDK (`google-genai`)
- **Service Catalog:** YAML (`PyYAML`)
- **HTTP:** `requests`
- **Config:** `.env` + environment variables (`python-dotenv`)
- **Reporting:** Excel export (`openpyxl`)
- **Email:** SMTP (Python standard library)
- **DB:** SQLite (Python standard library)

### Tooling (dev)

- **Testing:** `pytest`, `pytest-cov`
- **Linting:** `ruff`
- **Type checking:** `mypy`

---
## 📄 License

Source-available, non-commercial.  
You can read and run this code for evaluation, but you may not use it in production
or for commercial purposes without my written permission.
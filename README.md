# Automated Ticket Attribution

Project implements a small automation pipeline that simulates
automatic classification of IT helpdesk tickets based on an IT Service Catalog.

The goal is to:
- Fetch raw helpdesk requests.
- Fetch the Service Catalog.
- Use an LLM to classify tickets into `request_category`, `request_type`, and `sla`.
- Export the final dataset to an Excel report.
- Send the report via email.

---
## Tech Stack

- Python 3.10

---
## Project Structure

```text
automated_ticket_attribution/
  app/
    domain/                 # models
    infrastructure/         # integrations
    application/            # use-cases
  main.py                   # run app
  requirements.txt
  requirements-dev.txt
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
```bash
HELPDESK_API_URL
HELPDESK_API_KEY
HELPDESK_API_SECRET
SERVICE_CATALOG_URL
GEMINI_API_KEY
```
--- 
## How to Run

From the project root:

```bash
make run        # run the app
make test       # run unit tests (pytest)
make lint       # lint with ruff
make type-check # static type checking with mypy
```
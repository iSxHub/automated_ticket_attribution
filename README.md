# Automated Ticket Attribution

Project implements a small automation pipeline that simulates
automatic classification of IT helpdesk tickets based on an IT Service Catalog.

The goal is to:
- Fetch raw helpdesk requests from a webhook.
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
  README.md

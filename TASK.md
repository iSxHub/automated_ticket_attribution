## Technical Task: "Automated ticket attribution"

Your internal IT Helpdesk is facing high volume. Currently, support staff manually assigns every incoming request to a Category and Request Type to determine SLAs. You will build an automation pipeline where an AI model analyzes the request text, compares it against an IT Service Catalog, and classifies the request automatically.

## Objective

Build a small script/application that simulates this automation pipeline. Focus on clean code, error handling, and correct data manipulation. Any language is acceptable (Python, Go, Node.js, etc.).

## Requirements

1. Retrieve raw helpdesk request data from a webhook endpoint.
   Credentials are provided separately (API key + secret).
   - HELPDESK_API_URL: `<provided>`
   - HELPDESK_API_KEY: `<provided>`
   - HELPDESK_API_SECRET: `<provided>`

2. Retrieve the Service Catalog from a remote URL.
   - SERVICE_CATALOG_URL: `<provided>`

3. Classify each request using an LLM API:
   - Fill empty/zero fields: `request_category`, `request_type`, `sla_unit`, `sla_value`
   - Classification must be based on the Service Catalog

4. Populate the request_category, request_type, sla_unit and sla_value for each request.

5. For output, generate an Excel report (`.xlsx`):
   - Bold headers
   - Auto-fit columns (if possible)
   - Sort rows by:
     - `request_category` (ASC)
     - `request_type` (ASC)
     - `short_description` (ASC)

6. Send the resulting report via email to `example@gmail.com` with subject:
   - `Technical task - <your name and last name>`
   Include:
   - The report as an attachment
   - A link to the codebase
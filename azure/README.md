# Azure side

Resource group: `rg-b2b-agg-demo` (created via Bicep in `infra/`, location
matches Power Platform tenant region).

## Components

- `functions/function_app.py` — single Azure Functions **v4 (decorator
  model)** app exposing two HTTP routes:
  - `GET/POST /api/feed/{supplier_id}` — returns a supplier feed read from
    Blob; the "supplier API" stand-in. **MVP1**.
  - `POST /api/normalize-sku` — deterministic + fuzzy SKU matcher
    (`sku_matcher.py`, rapidfuzz), the fallback to AI Builder. **MVP2**.
- `functions/generate-quote-pdf` — Python, renders an RFQ Quote as PDF
  (reportlab) and uploads to Blob. **MVP3**.
- `logic-apps/supplier-sync-orchestrator` — HTTP-triggered Logic App that
  validates an incoming feed update and publishes to Service Bus topic
  `stock-updates`. **MVP2**.
- `infra/` — Bicep templates for the entire RG (Storage, Functions,
  Logic App, Service Bus, App Insights). **MVP3** (skeleton may appear
  earlier).

## Local dev

```bash
cd azure/functions          # the one function-app root (v4 model)
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
func start                  # serves /api/feed/{id} and /api/normalize-sku
```

Run the matcher's unit tests:

```bash
cd azure/functions && pip install pytest && pytest -q
```

## Deploy (manual, until Bicep workflow is wired)

```bash
az account set --subscription <subscription-id>
az group create --name rg-b2b-agg-demo --location westeurope

# Function App
func azure functionapp publish <function-app-name> --python
```

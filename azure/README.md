# Azure side

Resource group: `rg-b2b-agg-demo` (created via Bicep in `infra/`, location
matches Power Platform tenant region).

## Components

- `functions/fetch-supplier-feed` — Python, returns a mock supplier feed
  read from Blob; the "supplier API" stand-in. **MVP1**.
- `functions/normalize-sku` — Python, deterministic fuzzy matcher
  (rapidfuzz) used as fallback to AI Builder. **MVP2**.
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
cd azure/functions/fetch-supplier-feed
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
func start
```

## Deploy (manual, until Bicep workflow is wired)

```bash
az account set --subscription <subscription-id>
az group create --name rg-b2b-agg-demo --location westeurope

# Function App
func azure functionapp publish <function-app-name> --python
```

# fetch-supplier-feed

Azure Function (v4 Python programming model) that serves a supplier's product feed blob over HTTP.  
Called by the Power Automate custom connector `B2BAgg-SupplierFeed` as part of the supplier-sync integration pipeline.

---

## Endpoint

```
GET  /api/feed/{supplier_id}
POST /api/feed/{supplier_id}
```

Auth level: **Function** (caller must pass `?code=<function-key>` or `x-functions-key` header).

---

## Supported supplier IDs

| supplier_id | Alias | Container | Blob |
|---|---|---|---|
| `rosshinaopt` | `1` | `feed-supplier-en` | `feed.json` |
| `tyrecenter-spb` | `2` | `feed-supplier-ru` | `feed.json` |
| `koleso-ru` | `3` | `feed-supplier-xml` | `feed.json` |

Unknown IDs return **404**.

---

## Response

- `200 OK` — `application/json`, body is the raw feed payload
- `404 Not Found` — unknown supplier or missing local file
- `502 Bad Gateway` — blob exists but is not valid JSON
- `500 Internal Server Error` — storage access failure (details in App Insights)

Response headers include `X-Supplier-Id` and `X-Container` for tracing.

---

## Running locally

### Prerequisites

- Python 3.11
- [Azure Functions Core Tools v4](https://learn.microsoft.com/azure/azure-functions/functions-run-local)
- (optional) [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite) for local blob emulation

### Steps

```bash
# 1. Create a virtual environment
cd azure/functions
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Copy the settings template
cp local.settings.json.template local.settings.json
# Edit local.settings.json if needed (e.g. point LOCAL_FEEDS_PATH to real data)

# 3. Seed sample feed files (if not already present)
mkdir -p ../../data/feeds/feed-supplier-en
echo '{"supplier":"rosshinaopt","items":[]}' > ../../data/feeds/feed-supplier-en/feed.json

# 4. Start the function host
func start
```

With `AZURE_STORAGE_CONNECTION_STRING` set to `UseDevelopmentStorage=true` (the template default),  
the function reads from the local filesystem at `LOCAL_FEEDS_PATH` instead of Azure Blob Storage.

Test with curl:
```bash
curl "http://localhost:7071/api/feed/rosshinaopt?code=<any-value-in-local>"
```

---

## Required app settings

| Setting | Description |
|---|---|
| `AZURE_STORAGE_CONNECTION_STRING` | Connection string for the storage account that holds feed containers. Set to `UseDevelopmentStorage=true` for local dev. |
| `LOCAL_FEEDS_PATH` | (local dev only) Path to the directory that mirrors container layout. Default: `../../data/feeds` relative to function-app root. |
| `AzureWebJobsStorage` | Standard Functions storage binding. |
| `FUNCTIONS_WORKER_RUNTIME` | Must be `python`. |

In production these settings live in the Function App **Configuration** blade (or Key Vault references).

---

## Deploying to Azure

```bash
# One-time: create the function app via Bicep (see azure/infra/main.bicep)
az deployment group create \
  --resource-group rg-b2b-agg-demo \
  --template-file ../infra/main.bicep \
  --parameters ../infra/main.bicepparam

# Deploy the function code
cd azure/functions
func azure functionapp publish <function-app-name> --python
```

GitHub Actions CI/CD is wired in `.github/workflows/` (see that directory's README).

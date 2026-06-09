# Local setup

This repo is a working portfolio artifact, not a one-click deploy. The notes
below let you build and inspect the pieces locally. No secrets are committed —
supply your own via `.env.local` / environment variables.

## Tools

| Tool | Used for |
|---|---|
| Node.js 20+ | Buyer Code App (`apps/buyer-code-app`) |
| Python 3.11 | Azure Functions, seed/utility scripts |
| Azure Functions Core Tools v4 | run/deploy the Function locally |
| Power Platform CLI (`pac`) | solution pack/unpack/import/export, Code App |
| Azure CLI (`az`) + Bicep | infra build/deploy |

> macOS note: pac CLI 1.52.x (net9.0) is pinned because newer builds on
> .NET 10 can crash in the macOS auth broker. Use `pac auth ... --deviceCode`.
> See [`docs/adr/001-pac-cli-on-net9.md`](adr/001-pac-cli-on-net9.md).

## Buyer Code App

```bash
cd apps/buyer-code-app
npm install
cp .env.example .env.local      # fill in placeholders, or set VITE_USE_MOCK=true
npm run dev                     # lint: npm run lint, build: npm run build
```

`VITE_USE_MOCK=true` runs the app against bundled mock data with no Power
Platform connection. All `VITE_*` values in `.env.example` are placeholders.

## Azure Function

```bash
cd azure/functions
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                          # SKU-matcher test suite
func start                      # needs local.settings.json (gitignored)
```

## Environment configuration (placeholders only)

Never commit real values. Use these placeholders and supply real ones via
`.env.local`, `local.settings.json`, a gitignored `.bicepparam.local`, or CI
secrets:

```text
<tenant-id>
<subscription-id>
https://<your-dev-org>.crm.dynamics.com/
https://<your-test-org>.crm.dynamics.com/
https://<your-prod-org>.crm.dynamics.com/
```

## Power Platform solutions

Solution source under `solutions/` is the source of truth (unpacked XML/JSON).
Pack/import with `pac solution pack` / `pac solution import`. See
[`docs/governance.md`](governance.md) for the three-solution split and ALM flow.

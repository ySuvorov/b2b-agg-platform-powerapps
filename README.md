# B2B Market Intelligence & Supplier Aggregation Platform

A Power Platform reference implementation of a B2B marketplace that
aggregates inventory, pricing, and market intelligence across
heterogeneous supplier sources. Built as a portfolio piece to showcase
end-to-end competence across Microsoft Power Platform, Azure, and modern
ALM practices.

> **Domain**: B2B wholesale tire distribution (Russia market, Michelin-like).
> **Note**: The architecture is category-agnostic — the same pattern scales
> to auto-parts, building materials, or any heterogeneous B2B catalog.

---

## Highlights for reviewers

- **Pro-code Power Apps Code App** (React + TypeScript + Fluent UI v9) for the
  buyer experience, alongside a **Model-driven App** for operations admins.
- **Dataverse** as the system of record (12 entities, BPF, security roles).
- **AI Builder Custom Classification Model** auto-resolves heterogeneous
  supplier SKUs to a canonical product catalog with confidence-based routing.
- **Copilot Studio agent "MarketBot"** embedded in the Code App.
- **Azure-side**: Functions (Python), Logic Apps, Service Bus, Blob —
  simulating real third-party supplier APIs with three distinct schemas.
- **Power BI** workspace with regional demand forecasting, supplier scorecard,
  and data quality reports — tiles embedded into both apps.
- **Dual ALM**: Power Platform Pipelines (Dev → Test → Prod) *and*
  GitHub Actions using `pac` CLI for solution export/import.
- **Governance**: DLP policy documentation, multi-environment strategy,
  Service-Principal-based deployments.

## Architecture (high level)

See [`docs/architecture.md`](docs/architecture.md) for the full diagram and
component-by-component breakdown.

![Architecture](docs/diagrams/architecture.svg)

```
Buyer ──── Code App (React+TS) ──┐
Admin ─── Model-driven App ──────┼─→ Dataverse ←─→ Power Automate ─→ AI Builder
Analyst ── Power BI Workspace ───┘                       │
                                                         ├──→ Azure Functions ──→ Blob
                                                         ├──→ Logic App ──→ Service Bus
                                                         └──→ Copilot Studio agent
```

## Implementation status

| Component | Status | Notes |
|---|---|---|
| **Dataverse** — 7 tables, relationships, seed data | ✅ Done | 7 regions, 3 suppliers, 30 products, 193 offers in Dev |
| **Power Automate** — Supplier Sync flow | ✅ Done | Manual trigger → Azure Function → upsert b2b_supplieroffer |
| **Azure Function** `fetch-supplier-feed` | ✅ Done | Python v4, deployed to `func-b2bagg-dev.azurewebsites.net` |
| **Azure Infra** (Bicep) | ✅ Done | Functions, App Insights, Key Vault, Storage, Log Analytics |
| **Buyer Code App** (React + Fluent UI v9) | ✅ Done | Home / Search / Cart / Orders pages, 0 TS errors |
| **Model-driven App** `b2b_B2BAggOperations` | ✅ Done | Views + forms for all 7 entities |
| **Custom Connector** (OpenAPI → Azure Function) | 🔄 In progress | YAML ready at `azure/openapi/fetch-supplier-feed.yaml` |
| **AI Builder SKU Classifier** | ⏳ MVP2 | Custom text classification model |
| **Copilot Studio agent "MarketBot"** | ⏳ MVP2 | Embedded in Code App side panel |
| **Logic App + Service Bus** | ⏳ MVP2 | Push-based supplier ingestion |
| **Power BI workspace** | ⏳ MVP2 | Regional demand, supplier scorecard |
| **PP Pipelines** Dev → Test → Prod | ⏳ MVP2 | |
| **Power Pages** supplier portal | ⏳ MVP3 | External Entra B2B |

See [`PROGRESS.md`](PROGRESS.md) for current stage and detailed roadmap.

## Repository layout

```
.
├── CLAUDE.md            # operator's notes for AI-assisted sessions
├── PROGRESS.md          # current stage and what's next
├── docs/                # architecture, ADRs, governance, demo script
├── solutions/           # exported Dataverse solutions (XML, source of truth)
├── apps/
│   └── buyer-code-app/  # React+TS Power Apps Code App
├── azure/
│   ├── functions/       # Python Azure Functions
│   ├── logic-apps/      # Logic App workflow definitions
│   └── infra/           # Bicep IaC
├── powerbi/             # .pbix and report documentation
├── data/                # mock CSV seeds
├── scripts/             # seed scripts and helpers
├── deck/                # architecture deck (PPTX/PDF)
└── .github/workflows/   # CI for solution validation and deployment
```

## Quick start (for reviewers)

This repo is a working artifact, not a one-click deploy. To reproduce the
environment, see:

1. [`docs/setup-log.md`](docs/setup-log.md) — local tooling + tenant setup
2. [`docs/architecture.md`](docs/architecture.md) — what each component does
3. [`docs/governance.md`](docs/governance.md) — environments, solutions, ALM
4. [`deck/`](deck/) — the architecture deck used in the interview walkthrough

### Run the Buyer Code App locally

```bash
cd apps/buyer-code-app
npm install
npm run dev          # http://localhost:3000 — uses mock data fallback
```

For live Dataverse data, set in `.env.local`:
```
VITE_DATAVERSE_URL=https://YOUR-DATAVERSE-ORG.crm.dynamics.com
VITE_DEV_TOKEN=<az account get-access-token --resource https://YOUR-DATAVERSE-ORG.crm.dynamics.com>
```

### Deploy to Power Platform

```bash
# Build
cd apps/buyer-code-app && npm run build

# Push to Power Apps (requires Code Apps enabled in PP Admin Center for the env)
npx power-apps push

# Export solution after changes
pac solution export --name B2BAgg_Core --path solutions/ --overwrite
pac solution unpack --zipFile solutions/B2BAgg_Core.zip --folder solutions/B2BAgg.Core/src --allowDelete
```

## License

MIT — see [`LICENSE`](LICENSE).

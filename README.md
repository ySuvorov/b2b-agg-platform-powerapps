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

> The **Implementation status** table below is the source of truth for what is
> built vs. roadmap. This list describes the overall design ambition.

**Implemented today:**
- **Pro-code Power Apps Code App** (React + TypeScript + Fluent UI v9, Power Apps
  SDK + generated Dataverse services) for the buyer experience, alongside a
  **Model-driven App** for operations admins.
- **Dataverse** as the system of record — **10 custom tables** in `B2BAgg.Core`,
  with seed data (regions, suppliers, warehouses, canonical products, offers).
- **Azure Function** (Python) serving three deliberately heterogeneous supplier
  feeds (EN/RU/XML), with modular **Bicep** infra (Functions, App Insights, Key
  Vault, Storage, Service Bus, Logic App scaffolding).
- **Deterministic SKU-resolution engine** (size hard-gate + homologation/run-flat
  cap) with a real pytest suite wired into CI.
- **GitHub Actions ALM** on **OIDC federated credentials** (no client secret):
  PR validation gate, Dev deploy, Test/Prod import, and source export-via-PR.
- **Power Platform Pipelines** Dev → Test is green on Platform Host: Core,
  AI, and Integration are imported into Test as managed solutions.
- **Custom security role** `B2B Procurement Ops` and a **solution-aware supplier-
  sync flow** (`B2BAgg.Integration`, idempotent upsert on an alt-key triple).

**Roadmap / stretch / known limits:**
- Full Dev → Test → Prod Pipelines promotion across all solution modules.
- Test custom connector connection refs may need manual rebind before running
  `Sync Supplier Offers` / `Normalize SKU` in Test.
- Copilot Studio published channel/embed pending PAYG Copilot capacity.
- Power BI anonymous/public embed pending tenant Publish-to-web setting.
- Power Pages supplier portal.

## Architecture (high level)

See [`docs/architecture.md`](docs/architecture.md) for the full diagram and
component-by-component breakdown. The diagram source is
[`docs/diagrams/architecture.mmd`](docs/diagrams/architecture.mmd) (Mermaid).

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
| **Dataverse** — 11 tables, relationships, seed data | ✅ Done | 7 regions, 3 suppliers, 6 warehouses, 36 products, 201 seeded offers (≈262 live incl. flow rows) in Dev; `b2b_marketsignal` added in Stage 4 |
| **Buyer Code App** (React + Fluent UI v9) | ✅ Done | Power Apps SDK + generated services; Home / Search / Cart / **New RFQ** / Orders; multi-supplier cart auto-splits into one order per supplier; deployed & smoke-tested in Dev |
| **Model-driven App** `b2b_B2BAggOperations` | ✅ Done | Forms/views; sitemap exposes all 11 tables across Catalog / Operations / Inventory / Data Quality / **Intelligence** (Market Signals) areas |
| **Azure Function** `fetch-supplier-feed` | ✅ Done | Python v4, deployed to `func-b2bagg-dev.azurewebsites.net` |
| **Azure Infra** (Bicep) | ✅ Done | Functions, App Insights, Key Vault (refs), Storage, Service Bus, Logic App, Log Analytics |
| **SKU-resolution engine** + pytest in CI | ✅ Done | Deterministic cascade; tests gate PRs |
| **GitHub Actions ALM** (OIDC) | ✅ Done | PR gate + Dev deploy + Test/Prod import + export-via-PR, no client secret. GitHub Actions gates **`B2BAgg.Core`**; PP Pipelines promotes all three solutions (see [`docs/governance.md`](docs/governance.md)) |
| **Power Automate** — Supplier Sync flow | ✅ Done | Solution-aware (`B2BAgg.Integration`), connection refs + env vars, idempotent upsert on the alt-key triple. **As-built scope: single-supplier EN spine (Rosshinaopt); multi-supplier RU/XML fan-out is roadmap.** Raw HTTP Dataverse URLs use a placeholder host — set per-env via environment variable |
| **Power Automate** — RFQ Broadcast flow | ✅ Done | Power Apps (V2) trigger invoked from the Code App `/rfq/new`; fans out one `b2b_rfq` per selected supplier (status Sent); solution-aware in `B2BAgg.Integration`, wired via `npx power-apps add-flow` |
| **Custom security role** `B2B Procurement Ops` | ✅ Done | CRUD on the `b2b_*` tables; exported in `B2BAgg.Core` (audit A-4) |
| **Custom Connector** (OpenAPI → Azure Function) | ✅ Done | Two custom connectors exported in `B2BAgg.Integration` (`b2b_fetchsupplierfeed`, Normalize SKU); OpenAPI at `azure/openapi/fetch-supplier-feed.yaml` |
| **BPF on `b2b_order`** | ✅ Done | `B2B Order Lifecycle` active on `b2b_order`, exported in `B2BAgg.Core` |
| **AI Builder SKU Classifier** | ✅ Done | Custom text classification model in `B2BAgg.AI`; deterministic matcher remains the primary production path |
| **Copilot Studio agent "MarketBot"** | ✅ Done | Hybrid: generative answers over Dataverse (price compare, inventory, with citations) + deterministic **Create RFQ** topic → Power Automate → Dataverse → MDA (ADR-006). Publish to a live channel needs Copilot Studio PAYG capacity (out of demo budget) — demoed from the test canvas; Code App embed pending capacity |
| **Power BI workspace** | ✅ Done | Workspace `B2BAgg-Analytics`; report **B2BAgg Market Intelligence** (4 pages, 27 visuals) **code-generated** via Fabric PBIR REST, bound to live Dataverse; embedded as tiles in the Code App `/insights` |
| **PP Pipelines** Dev → Test | ✅ Done | Native Platform Host pipeline `B2BAgg Dev to Test`; Test has managed `B2BAgg_Core` `1.0.0.1`, `B2BAgg_AI` `1.0.0.0`, `B2BAgg_Integration` `1.0.0.1` |
| **Power Pages** supplier portal | ⏳ Roadmap | External Entra B2B |

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
npm run dev          # http://localhost:3000
```

Live Dataverse data is brokered through the **Power Apps SDK** (generated
services in `src/generated/`) once the app is pushed to the environment — there
is no dev-token / raw-fetch path. For purely offline UI work, opt into mock data
explicitly with `VITE_USE_MOCK=true` in `.env.local`.

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

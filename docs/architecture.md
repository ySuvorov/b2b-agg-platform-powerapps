# Architecture

> ℹ️ **Target architecture vs. current build.** This document describes the full
> intended platform. For what is actually implemented today, see the
> **Implementation status** table in [`README.md`](../README.md).
>
> **Implemented demo path (end-to-end, real):** Buyer Code App (Power Apps SDK)
> searches live Dataverse offers → cart → per-supplier order creation → `/rfq/new`
> RFQ broadcast → review in the Model-driven App; deterministic SKU matcher with
> CI tests; AI Builder classifier; Azure Function serving heterogeneous feeds;
> Supplier Sync / Normalize SKU / Low Stock Alert / Redistribution Advisor flows
> writing `b2b_marketsignal`; BPF `B2B Order Lifecycle` + custom security role;
> Copilot "MarketBot"; Power BI tiles on `/insights`; GitHub Actions OIDC ALM
> (PR gate, deploy, export) plus PP Pipelines Dev → Test.
>
> **Roadmap / stretch (described below, not yet built):** 20-warehouse scale
> (currently **6** regional DCs seeded), multi-supplier RU/XML sync fan-out
> (current sync is a single-supplier EN spine), and the Power Pages supplier
> portal.
>
> **Warehouse semantics (audit A-1):** warehouses are **platform-owned regional
> distribution centres** (`b2b_warehouse → b2b_region`), not supplier-operated.
>
> **Orders (audit A-2):** `b2b_order` is a lightweight checkout artifact (order
> number, status, total, currency). Buyer/account is not modelled (no buyer
> entity in this MVP); supplier is implicit via the per-supplier cart split, and
> region is reachable through the offer's warehouse.

## Context

Buyers (mid-sized wholesale tire retailers) want one place to search inventory
across many heterogeneous supplier sources, get competitive prices, and
combine line items into a single procurement workflow. Suppliers publish
inventory in incompatible formats with inconsistent SKU naming. Operations
needs a way to normalize, govern, and analyze that data.

This system delivers:

1. A unified canonical product catalog over heterogeneous supplier feeds.
2. AI-assisted SKU normalization with admin review for low-confidence cases.
3. A multi-supplier purchasing experience for buyers, including RFQ/quote flow.
4. Regional/seasonal market intelligence on top of aggregated data.
5. **Platform-owner analytics layer**: real-time stock visibility across
   7 federal districts and 20 warehouses, deficit detection, and redistribution
   recommendations — the primary internal ROI driver behind the B2B portal.

## Personas & surfaces

| Persona | Surface | Stack |
|---|---|---|
| Buyer | **Power Apps Code App** | React + TypeScript + Vite + Fluent UI v9 + Power Apps SDK |
| Operations / Procurement Admin | **Model-driven App** on Dataverse | Forms, views, BPF, security roles |
| Market Analyst | **Power BI workspace** + embedded tiles | Dataverse direct query |
| Supplier (MVP3) | **Power Pages portal** | External Entra B2B + portal forms |

## High-level diagram

```mermaid
flowchart LR
  subgraph Users
    B[Buyer]:::p
    A[Admin]:::p
    N[Analyst]:::p
  end

  subgraph "Power Platform"
    CA["Code App<br/>(React+TS)"]
    MDA["Model-driven App"]
    PB["Power BI Workspace"]
    CS["Copilot Studio<br/>MarketBot"]
    AB["AI Builder<br/>SKU Classifier"]
    PA["Power Automate<br/>Flows"]
    DV[("Dataverse")]
  end

  subgraph "Azure"
    LA["Logic App<br/>Supplier sync orchestrator"]
    SB["Service Bus<br/>topic: stock-updates"]
    AF["Azure Functions<br/>fetch-feed, normalize-sku, gen-pdf"]
    BLOB["Blob Storage<br/>mock supplier feeds (3 schemas)"]
    AI[/"Application Insights"/]
  end

  B --> CA
  A --> MDA
  N --> PB
  CA -.embed.- CS
  CA -.embed tile.- PB
  MDA -.embed chart.- PB

  CA <--> DV
  MDA <--> DV
  PB <--> DV
  CS --> PA
  PA <--> DV
  PA <--> AB
  PA -->|"custom connector"| AF
  PA -->|"trigger"| LA

  LA --> SB
  LA --> BLOB
  SB -->|"subscription"| PA
  AF --> BLOB
  AF --> AI

  classDef p fill:#f9f,stroke:#333
```

## Component responsibilities

### Power Platform layer

**Dataverse** — system of record. 12 entities. See `docs/data-model.md`.

**Buyer Code App** (`apps/buyer-code-app/`):
- `/` — Home: alerts, last order, KPIs
- `/search` — cross-supplier search; **headline feature**: two-level results table.
  Level 1: one row per canonical SKU (brand, model, size, total stock, min price).
  Level 2 (expand row): offers per warehouse with city, year, country, lead time,
  актуальность, stock, price. Filters: Ширина / Профиль / Диаметр / Сезон /
  Город / Бренды / Год / Поставщики. Quick-pick: Popular sizes matrix R13–R21.
  See `docs/references/` for UI reference screenshots.
- `/cart` — multi-supplier cart, automatically split into per-supplier orders
- `/rfq/new` — RFQ composer, triggers `RFQ Broadcast` flow
- `/orders` — history with BPF tracker
- `/insights` — embedded Power BI tile (price trend for last search)
- Side panel: Copilot Studio chat (MarketBot)

**Operations Model-driven App**: three areas.
- Catalog: Suppliers, **Warehouses**, Canonical Products, Regions
- Operations: Orders (BPF), RFQs, Quotes, **Data Conflicts queue**, Audit
- Integrations: Import Jobs, Flow runs, Connector health

The **Data Conflicts queue** is a Kanban-style view (Pending / Suggested /
Auto-resolved) with a custom form action **"Suggest match"** that calls AI
Builder synchronously and lets the operator Approve/Reject.

**Power BI workspace** `B2BAgg-Analytics`. Reports:
1. Regional Demand & Forecast (DAX-driven seasonal extrapolation; not ML)
2. Supplier Scorecard (fill rate, price competitiveness, sync reliability)
3. Data Quality Trends (% auto-resolved, AI confidence distribution)
4. Top-moving SKUs by region
5. **Stock Distribution Map** — heatmap of stock by district/city (platform owner)
6. **Redistribution Advisor** — table of deficit alerts with recommended source

Datasource: Dataverse direct query. Tiles embedded in both Code App and MDA.

#### Platform owner analytics — key Power BI slicers

The platform's primary internal value is visibility across all 20 warehouses
in real time. Power BI slicers planned:

| Slicer | Grain | Use case |
|---|---|---|
| Federal district | 7 districts | Compare regions by stock / demand |
| City | 20+ cities | Locate nearest surplus for redistribution |
| Season | Summer / WinterStudded / WinterFriction / AllSeason | Seasonal planning |
| Brand / Model | canonical SKU | Track specific product performance |
| Week / Month | time | Demand dynamics, YoY comparison |
| Supplier | 3 sources | Reliability and fill rate per supplier |

**Redistribution logic (Stock Redistribution Advisor flow, MVP2):**

```
For each canonical SKU:
  For each district D:
    stock_D = SUM(supplieroffer.stock) WHERE warehouse.region = D
    IF stock_D < threshold_low:
      Find adjacent district A with stock_A > threshold_high
      Create MarketSignal(type=RedistributionAdvice, region=D, targetregion=A,
                          severity=Warning/Critical based on gap)
```

Thresholds are stored as environment variables (Power Platform Env Variables).
Adjacency between districts is a static lookup table in Dataverse or hardcoded
in the flow (7 nodes, simple map: ЦФО↔СЗФО, ЦФО↔ПФО, ПФО↔УрФО, etc.).

**Power Automate flows** (`B2BAgg.Integration` solution):
1. *Hourly Supplier Sync (parent)* — scheduled, dispatches to child flows
2. *Sync supplier (child)* — calls custom connector → Function → upserts offers
   (upsert key: warehouse + rawsku)
3. *Normalize SKU* — instant trigger on new/updated offer, calls AI Builder,
   creates a DataConflict if confidence < 0.85
4. *RFQ Broadcast* — button trigger from app, fan-out to suppliers, waits
   for Quotes or 24h timeout
5. *Order Approval BPF* — stage transitions, Teams notifications
6. *Low Stock Alert* — Dataverse trigger → Teams Adaptive Card
7. *Conflict Auto-Resolve Sweeper* — daily recompute of unresolved conflicts
8. *Stock Redistribution Advisor* — daily scan across districts, creates
   RedistributionAdvice MarketSignals visible in MDA and Power BI (MVP2)

**AI Builder**:
- Custom Text Classification model: raw supplier name → canonical product ID
  + confidence. Trained on ~150 labeled pairs. Threshold 0.85 for auto-resolve.
- (MVP3) Form Processing: PDF price-list → structured rows.

**Copilot Studio agent "MarketBot"**: embedded in Code App side panel.
Topics include product lookup, price comparison, RFQ creation, regional
demand queries. Calls Power Automate flows and Dataverse via generated actions.

### Azure layer

`rg-b2b-agg-demo` resource group, region matching Power Platform tenant.

- **Storage Account** with 3 Blob containers, each holding a JSON feed in a
  **different schema** (EN field names, RU/transliterated field names,
  pseudo-XML wrapped in JSON). This is the deliberate "real-world heterogeneity"
  signal — proves the architecture handles inconsistent inputs.
- **Azure Functions** (Consumption, Python 3.11):
  - `fetch-supplier-feed(supplier_id)` — returns the mock feed JSON
  - `normalize-sku(raw_name)` — deterministic fuzzy matcher with `rapidfuzz`,
    used as a fallback for AI Builder
  - `generate-quote-pdf(rfq_id)` — renders a PDF (reportlab) and uploads to Blob
- **Logic App** (Consumption): HTTP trigger → schema validation →
  publish to Service Bus topic
- **Service Bus**: namespace + topic `stock-updates`, two subscriptions
  (`to-power-automate`, `to-analytics`). See ADR-003 for Standard vs Basic.
- **Application Insights**: telemetry for Functions and Logic App
- **Custom connectors** (in PP): OpenAPI wrappers over the Functions, API
  key auth in dev (Service Principal in MVP3)

## Data flow — supplier sync (MVP2)

```mermaid
sequenceDiagram
  participant SCHED as PA Scheduler
  participant CONN as Custom Connector
  participant FN as fetch-supplier-feed
  participant BLOB as Blob (mock feed)
  participant DV as Dataverse
  participant NORM as Normalize SKU flow
  participant AB as AI Builder
  participant CONF as DataConflict queue

  SCHED->>CONN: invoke per supplier
  CONN->>FN: GET feed
  FN->>BLOB: read JSON
  FN-->>CONN: feed
  CONN-->>SCHED: rows
  SCHED->>DV: upsert SupplierOffer (with raw_name)
  DV-->>NORM: trigger (new offer)
  NORM->>AB: classify(raw_name)
  AB-->>NORM: canonical_id, confidence
  alt confidence ≥ 0.85
    NORM->>DV: link offer→canonical
  else
    NORM->>CONF: create conflict
  end
```

For MVP2 the *Logic App + Service Bus* path is added as an alternative push
ingestion: a supplier system POSTs to the Logic App, which validates and
publishes to the SB topic; a PA flow subscribes and runs the same downstream
normalization. This demonstrates two integration patterns (pull and push)
with the same back-end normalization.

## Security & roles

Dataverse security roles in `B2BAgg.Core`:

| Role | Read | Write | Delete | Notes |
|---|---|---|---|---|
| Buyer | own Orders/RFQs, all Products/Suppliers | own Orders/RFQs | — | Buyer Code App users |
| OperationsAdmin | all | all (except security) | own audit | MDA users |
| Analyst | all (read-only) | — | — | Power BI consumers |
| SystemAdmin | all | all | all | full control |

Authentication: Entra ID (Microsoft) tenant accounts. Service Principal for
GitHub Actions deployment (MVP3).

## ALM

See `docs/governance.md` for full detail.

Highlights:
- Three environments: Dev → Test → Prod (Developer-tier each, on the
  Power Platform Developer Plan).
- Three solutions: `B2BAgg.Core`, `B2BAgg.AI`, `B2BAgg.Integration`.
- **Two parallel deployment paths**, both demonstrated:
  1. Power Platform Pipelines (Dev → Test → Prod, configured in PP admin).
  2. GitHub Actions using `pac` CLI for solution pack/unpack, validation,
     and import.
- Solution checker as a PR check.

## Verification (per MVP)

### MVP1 smoke test
1. Open Buyer Code App → search "Michelin Pilot Sport 4" → see 2 supplier offers
2. Add to cart → submit order
3. In Operations MDA: see the new Order → open BPF → progress one stage
4. Manually run `Hourly Supplier Sync` flow → see `ImportJob` created

### MVP2 end-to-end test
1. POST a mock new-offer payload to the Logic App HTTP endpoint
2. Confirm message appears in Service Bus topic
3. Confirm PA subscriber flow runs and creates a SupplierOffer
4. Confirm `Normalize SKU` flow auto-resolves (confidence ≥ 0.85) OR creates
   a DataConflict (visible in MDA Kanban view)
5. Confirm Power BI report refresh shows the new offer in inventory totals
6. Use Copilot side panel: "compare Continental Premium 5 across suppliers"
   → assistant returns Adaptive Card with table

### MVP3 readiness
1. PR open → solution checker passes
2. `deploy-test.yml` manual dispatch → solution imported into Test
3. PP Pipelines page shows successful Dev → Test deployment
4. Supplier portal (Power Pages) login works for external test account

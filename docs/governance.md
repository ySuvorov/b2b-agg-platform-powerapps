# Governance: environments, solutions, ALM, DLP

## Environment strategy

Three environments on the Power Platform Developer Plan, all of type
**Developer** (a single user is system admin). Promotion is strictly
Dev → Test → Prod; nothing is built directly in Test or Prod.

| Env | Purpose | Source of changes | Imported as |
|---|---|---|---|
| Dev | All authoring (tables, flows, apps) | direct edits | unmanaged solution |
| Test | UAT / smoke + integration tests | import from Dev | **managed** |
| Prod | Demo target / "production" | import from Test (or Dev for stretch) | **managed** |

Rationale: managed solutions in Test and Prod prevent ad-hoc UI tinkering
and enforce that the source of truth is the solution package exported from Dev.

## Solution strategy

Target design = three solutions, each a separately deployable unit, using
connection references and environment variables so the same package moves across
envs without modification.

| Solution | Contents | Status |
|---|---|---|
| `B2BAgg.Core` | Dataverse tables, columns, choices, MDA, Code App, **custom security role** `B2B Procurement Ops`, **BPF** `B2B Order Lifecycle` | **implemented** (exported to `solutions/B2BAgg.Core/`) |
| `B2BAgg.Integration` | Power Automate flows (Supplier Sync, RFQ Broadcast, Normalize SKU, Low Stock Alert, Redistribution Advisor), **two custom connectors**, connection references, environment variables | **implemented** (exported to `solutions/B2BAgg.Integration/`) |
| `B2BAgg.AI` | AI Builder Custom Classification model, Copilot Studio agent definitions | **implemented** (exported to `solutions/B2BAgg.AI/`) |

> **Current state (do not overclaim):** all three solutions are exported. A real
> custom **security role** (`B2B Procurement Ops`, CRUD on the `b2b_*` tables) and
> the **BPF** `B2B Order Lifecycle` are exported in Core. The supplier-sync flow
> is a single-supplier EN spine (Rosshinaopt); multi-supplier RU/XML fan-out is
> roadmap. GitHub Actions gates `B2BAgg.Core` only; **PP Pipelines** promotes all
> three solutions Dev → Test.

Each solution has its own version (`x.y.z`) tracked in `solutions/<name>/Other/Solution.xml`.

### BPF on `b2b_order` — `B2B Order Lifecycle` (Stage 4, ~15 min portal step)

A Business Process Flow is the one component best built in the App designer
(hand-authoring the BPF `clientdata` via API is brittle), so this is a **YS
designer step** (Stage 4 task Y2 — step-by-step RU walkthrough:
[`docs/handoff/order-bpf-ru.md`](handoff/order-bpf-ru.md)). Live `b2b_order.b2b_status` choices are
**Draft (100000000) → Confirmed (100000001) → Shipped (100000002)** — the BPF
stages map 1:1 to them. To build it:

1. [make.powerapps.com](https://make.powerapps.com) → env **B2BAgg-Dev** →
   **Solutions → B2BAgg.Core → New → Automation → Process → Business process flow**.
2. Name **"B2B Order Lifecycle"**, table **Order** (`b2b_order`) → Create.
3. In the designer add **three stages** on `b2b_order`, each with one data step
   (uses live columns only — `b2b_order` has `b2b_status`, `b2b_total_amount`,
   `b2b_currency_code`, `b2b_order_number`; do **not** reference buyer/supplier/
   region — those lookups are not on the live table):
   - **Draft** — data step: `b2b_order_number` (required).
   - **Confirmed** — data step: `b2b_total_amount` (required).
   - **Shipped** — data step: `b2b_status` (required).
4. **Save → Activate**.
5. It lands in `B2BAgg.Core` (created inside the solution). Tell Claude →
   `pac solution export B2BAgg_Core` re-captures it into `solutions/B2BAgg.Core/src`
   (the previously empty `<Workflows/>` will then carry the BPF definition).

> The 5-stage list in `docs/data-model.md` (Cart → Submitted → PO → Shipped →
> Fulfilled) is aspirational; the **live, shipped** lifecycle is the 3-stage
> Draft → Confirmed → Shipped above.

## Dual deployment paths

The demo deliberately ships **both** so the reviewer sees both worlds.

### Path A — Power Platform Pipelines (native)

Configured in the **Pipelines** environment in PP admin center. Stages:
`B2BAgg-Dev` → `B2BAgg-Test` → `B2BAgg-Prod`. Approvals required at Test→Prod.
Used for ad-hoc promotions and for the live demo walkthrough.

### Path B — GitHub Actions + `pac` CLI

Source of truth is `solutions/` in the repo (unpacked solution XML, friendly
to git diff). Workflows under `.github/workflows/`:

| Workflow | Trigger | Purpose |
|---|---|---|
| `pr-validation.yml` | PR → `main` | `pac solution check` + lint/build Code App + compile Function + SKU-matcher pytest |
| `deploy-dev.yml` | dispatch + push to `main` (`solutions/**`) | pack → import (unmanaged) into Dev |
| `export-solution.yml` | manual dispatch | `pac solution export` from Dev/Test → unpack → **open a PR from a bot branch** |
| `deploy-test.yml` | manual dispatch | pack → `pac solution import` into Test |
| `deploy-prod.yml` | manual dispatch | pack managed → import into Prod (manual run = the approval gate) |

Authentication: **GitHub Actions OIDC + Entra federated credentials — no client
secret in repo or CI** (the old `PP_CLIENT_SECRET` was deleted from GitHub and
Entra in audit P0/P3). The app is added as an application user to each
environment with a deploy-capable role. See `.github/workflows/README.md` and
`docs/ci-secrets-todo.md`. (There is no Bicep what-if in CI today — roadmap.)

## DLP policies (documented, partially enforced)

Connector tenant-level grouping intent:

| Group | Connectors |
|---|---|
| Business | Dataverse, Office 365 Outlook (internal), SharePoint, Teams, Power BI, custom connectors to our own Azure Functions |
| Non-Business | HTTP, HTTP with Entra ID (only via approved patterns), Twitter, public web services |
| Blocked | any connector with file-system or arbitrary HTTP that hasn't been whitelisted |

A real prod tenant would enforce these; on the Developer Plan we
document the policy in this file and demonstrate it on a single environment.

## Audit & monitoring

- **Dataverse audit** is enabled on key tables (see `docs/data-model.md`).
- **Power Automate run history** is reviewable inside the MDA via an
  embedded view.
- **Application Insights** captures Function/Logic App logs and traces.
- **Solution version history** lives in git (`solutions/.../Solution.xml`).

## Secrets handling

- Local dev: `.env.local` (gitignored). Loaded by scripts that need credentials.
- CI/CD: GitHub Actions secrets at the repo level. Federated OIDC for Azure
  + Power Platform Service Principal — **no long-lived secrets in repo**.
- Runtime: Azure Function app settings reference Key Vault (`@Microsoft.KeyVault(...)`).
- Power Automate / custom connectors: environment variables in solution,
  references resolved per-environment.

## Cost guardrails

- Service Bus namespace **stopped** outside demo windows (saves ~$0.30/day on Standard).
- Function app Consumption — cost is ~zero under demo traffic.
- Logic App Consumption — first 4000 actions free.
- Power BI: free workspace or 60-day Pro trial for embedded tiles.
- Track monthly spend via Cost Management dashboard tile.

See ADR-002 for the Free vs PAYG decision and ADR-003 for the Service Bus
tier decision (Standard vs Basic + dual queues).

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
| `B2BAgg.Core` | Dataverse tables, columns, choices, MDA, Code App, **custom security role** `B2B Procurement Ops` | **implemented** (exported to `solutions/B2BAgg.Core/`) |
| `B2BAgg.Integration` | Power Automate supplier-sync flow, connection references, environment variables (Function base URLs, API key via env var) | **implemented** in audit **P5** (exported to `solutions/B2BAgg.Integration/`) |
| `B2BAgg.AI` | AI Builder Custom Classification model, Copilot Studio agent definitions | roadmap (not yet exported) |

> **Current state (do not overclaim):** `B2BAgg.Core` + `B2BAgg.Integration` are
> exported. A real custom **security role** (`B2B Procurement Ops`, CRUD on the
> `b2b_*` tables) is exported in Core (audit A-4). **BPF is roadmap** — a designer
> recipe is below. `B2BAgg.AI` is deferred per `docs/schema-canonical.md`.

Each solution has its own version (`x.y.z`) tracked in `solutions/<name>/Other/Solution.xml`.

### BPF on `b2b_order` — designer recipe (roadmap, ~5 min portal step)

A Business Process Flow is the one component best built in the App designer
(hand-authoring the BPF `clientdata` via API is brittle). To add it:

1. [make.powerapps.com](https://make.powerapps.com) → env **B2BAgg-Dev** →
   **Solutions → B2BAgg.Core → New → Automation → Process → Business process flow**.
2. Name **"B2B Order Lifecycle"**, table **Order** (`b2b_order`) → Create.
3. In the designer add three stages on `b2b_order`:
   **Draft → Confirmed → Shipped** (one stage per `b2b_status` option; add a data
   step in each, e.g. require `b2b_total_amount` in Confirmed).
4. **Save → Activate**.
5. It's already in `B2BAgg.Core` (created inside the solution). Tell Claude →
   `pac solution export` re-captures it into `solutions/B2BAgg.Core/src`.

Until then, BPF is marked roadmap (not an audit gap — see
`docs/audit/decisions-and-non-issues.md`).

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

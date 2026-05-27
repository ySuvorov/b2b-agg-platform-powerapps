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

Three solutions, each a separately deployable unit. Connection references and
environment variables are used so the same solution moves across envs without
modification.

| Solution | Contents |
|---|---|
| `B2BAgg.Core` | All Dataverse tables, columns, choices, BPF, security roles, MDA, Code App |
| `B2BAgg.AI` | AI Builder Custom Classification model, Copilot Studio agent definitions |
| `B2BAgg.Integration` | Custom connectors, Power Automate flows, connection references, environment variables (Azure Function base URLs, API keys via Key Vault refs) |

Each solution has its own version (`x.y.z`) tracked in `solutions/<name>/Other/Solution.xml`.

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
| `pr-validation.yml` | PR opened/updated | `pac solution check` + lint Code App + Bicep what-if |
| `export-solutions.yml` | manual / nightly | `pac solution export` from Dev → unpack → commit changes |
| `deploy-test.yml` | manual dispatch | pack solution → `pac solution import` into Test |
| `deploy-prod.yml` | release tag `vX.Y.Z` | pack managed → import into Prod |

Authentication: **Service Principal** (Entra app + federated credentials for
GitHub Actions OIDC, no client secret in repo). In Dev plan limitations the
SP must be added as an application user to each environment with the right
security role.

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

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

## Project status

See [`PROGRESS.md`](PROGRESS.md) for current stage and roadmap.

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

## License

MIT — see [`LICENSE`](LICENSE).

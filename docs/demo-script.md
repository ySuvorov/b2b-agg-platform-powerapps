# Demo script (Loom walkthrough)

> Placeholder — finalized in MVP3 once all features exist. Below is the
> shape; fill in concrete clicks per scene as we build.

Total target: **5–10 minutes**. Six acts × ~1 min, plus 30s intro/outro.

## Intro (0:00–0:30)
"This is a B2B tire market aggregator I re-built on Power Platform. It
unifies inventory from heterogeneous wholesale suppliers, applies AI-based
SKU normalization, and gives buyers a single multi-supplier purchasing
experience. Real version of this project ran on a different stack; here
I'm showing what the Power Platform implementation looks like."

## Act 1 — Buyer experience (Code App)
- Search "Michelin Pilot Sport 4 225/45 R17"
- Show one canonical SKU expanding into 3 supplier offers sorted by total
  landed cost, with stock and lead-time badges
- Add two offers from different suppliers into the cart → checkout
- "Notice the cart auto-splits into per-supplier orders"

## Act 2 — Behind the scenes (Power Automate + Service Bus)
- Open Power Automate run history
- Show the `Hourly Supplier Sync` parent flow with child flow per supplier
- Show Service Bus message inspector — one message published, two
  subscriptions consumed it

## Act 3 — AI normalization
- Add a new supplier feed (different schema: Russian field names)
- Trigger sync
- Show AI Builder model output: 8/10 SKUs auto-resolved (confidence ≥ 0.85)
- 2 SKUs land in the **Data Conflicts** queue with AI suggestions

## Act 4 — Admin & analytics (MDA + Power BI)
- Operations admin view: Kanban-style Conflicts queue
- Operator clicks "Approve" on one AI suggestion → flow updates the offer
- Switch to embedded Power BI tile: Regional Demand by climate zone,
  Supplier Scorecard

## Act 5 — Copilot Studio agent
- Open Code App side panel
- Type: "compare Continental Premium 5 across suppliers for Volga region"
- Show Adaptive Card response with table
- Type: "create RFQ for the top 3 offers" → flow triggers

## Act 6 — DevOps / Governance
- Switch to GitHub repo: PR with solution diff
- Show passing `pr-validation` action (solution checker, Bicep what-if)
- Open Power Platform Pipelines: Dev → Test → Prod stages, last run
- Briefly highlight environment + solution strategy diagram

## Outro (last 30s)
"Repo, deck, and ADRs are linked below. Happy to walk through any component
in depth."

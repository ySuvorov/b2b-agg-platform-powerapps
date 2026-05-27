# Buyer Code App

Power Apps Code App (React + TypeScript + Vite + Fluent UI v9) for the
wholesale buyer persona.

> **Not scaffolded yet** — will be created with `pac code init` at the start
> of MVP1 (Code App shell), then iterated through MVP2 (multi-supplier cart,
> RFQ composer, Copilot side panel).

## Planned pages

| Route | Purpose | Phase |
|---|---|---|
| `/` | Home — alerts, last order, KPI cards | MVP1 |
| `/search` | Cross-supplier search with filters | MVP1 |
| `/cart` | Multi-supplier cart (auto-split) | MVP2 |
| `/rfq/new` | RFQ composer | MVP2 |
| `/orders` | Order history + BPF tracker | MVP1 |
| `/insights` | Embedded Power BI tile | MVP2 |

## Side panel

Copilot Studio agent "MarketBot" embedded as an iframe panel from MVP2.

## Local dev (once scaffolded)

```bash
cd apps/buyer-code-app
npm install
npm run dev          # local Vite dev server, pac dev proxy
pac code push        # deploy to Power Apps
```

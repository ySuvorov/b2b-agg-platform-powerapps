# Power BI

Workspace (cloud): `B2BAgg-Analytics`. Reports are built **in the browser**
(Power BI Service web-authoring) — there is no Power BI Desktop on macOS. See
[`SETUP.md`](SETUP.md) for the full step-by-step.

> **Demo data source:** an **import semantic model** built from
> [`B2BAgg-Analytics-data.xlsx`](B2BAgg-Analytics-data.xlsx) — the real seed data
> (201 offers / 36 products / 6 warehouses / 7 regions / 3 suppliers),
> regenerated from `data/seed/*.csv` by [`gen-workbook.py`](gen-workbook.py).
> A real-time **push dataset** (`B2BAgg Market Data`) with the same data is also
> provisioned by [`../scripts/setup-powerbi.py`](../scripts/setup-powerbi.py).
>
> **Production target:** Dataverse **DirectQuery** (live system of record). Not
> used for the demo because the Power BI licence and the Dataverse admin
> currently live on different identities; documented as the prod path.

## Reports (built per SETUP.md)

| Report | Key measures | Phase |
|---|---|---|
| Regional Demand & Stock | Total Stock, Stock by Region, Low Stock Alert | MVP2 |
| Supplier Scorecard | Fill Rate %, Price Competitiveness %, Supplier Stock Rank | MVP2 |
| Top-moving SKUs | Stock Rank, Best Price, Inventory Value | MVP2 |
| Price Spread & Competitiveness | Price Spread, Summer vs Winter Ratio, Brand Price Premium | MVP2 |
| Orders (optional) | Total Revenue, Realised Revenue, Cancellation Rate % | MVP2 |

Measures: [`measures.dax`](measures.dax) (~24, single flat table — no
relationships needed).

## Artifacts

- `B2BAgg-Analytics-data.xlsx` — import workbook (upload source).
- `measures.dax` — DAX measures, grouped by report.
- `workspace-ids.example.json` — workspace + dataset ID template (real `workspace-ids.json` is gitignored).
- `gen-workbook.py` — regenerates the workbook from seed CSVs.

## Embedding

- Tile from "Regional Demand & Stock" → Code App `/insights`.
- Dashboard chart → Operations MDA.

Licensing: embedded tiles require Power BI Pro on the consuming user; the trial
covers the demo window.

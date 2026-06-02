# Power BI Setup Guide — B2BAgg Analytics (browser / Mac-safe)

> **No Power BI Desktop required.** Power BI Desktop has no macOS build, so this
> guide builds everything via the **Power BI Service / Fabric REST API** + browser.
> Tested path for a Mac-only operator.

## ✅ AS-BUILT (2026-06-01) — the report is now fully code-generated

The final pipeline turned out **more headless than this guide originally assumed**:

| Layer | How it was actually built | Artifact |
|---|---|---|
| Workspace | headless via REST | `B2BAgg-Analytics` (`<workspace-id>-…`) |
| Semantic model | **live Dataverse connector** (browser, Get data → Dataverse, Import) | `dataverse_report` (`0e72f1a8-…`) — tables `b2b_supplieroffer`, `b2b_canonicalproduct`, `b2b_supplier`, `b2b_region` |
| DAX measures | typed once in web data-model editor | 18 measures on `b2b_canonicalproduct` |
| **Report (4 pages, 27 visuals)** | **100% code via Fabric REST + PBIR** — `powerbi/build_report.py` | `B2BAgg Market Intelligence` (`<report-id>-…`) |

**Report build is reproducible from code** (`python3 powerbi/build_report.py`,
idempotent create/update via Fabric Items API). Visuals bind to the live model by
`semanticmodelid`, so a re-run after model changes just re-pushes the PBIR. This is
the real ALM story: the report definition lives in git, not only in the service.

- Helpers: `powerbi/fabric_lib.py` (token + LRO-aware Fabric REST calls).
- Pages: Regional Demand · Supplier Scorecard · Top-Moving SKUs · Price Spread.
- Source of truth for the live data is **Dataverse** (201 offers / 36 products /
  3 suppliers / 6 cities), queried directly — not the seed xlsx.

> The Excel/push-dataset paths below (Path A / B) are kept as **fallbacks** only.
> The Dataverse-connected, code-generated report above supersedes them.

---

> The workspace and a real-data dataset are already provisioned headless by
> `scripts/setup-powerbi.py`. You only build the **visuals** in the browser.

## Status (already done by Claude, headless)

| Item | Value |
|---|---|
| Workspace | **B2BAgg-Analytics** — id `<workspace-id>` |
| Push dataset | **B2BAgg Market Data** — real seed data (201 offers / 3 suppliers / 7 regions) |
| Import workbook | [`powerbi/B2BAgg-Analytics-data.xlsx`](B2BAgg-Analytics-data.xlsx) — 201 offers + 7 orders |
| Measures | [`powerbi/measures.dax`](measures.dax) — ~24 DAX measures (single flat table) |
| IDs | [`powerbi/workspace-ids.json`](workspace-ids.json) |

Data is the same set the idempotent seeder loads into B2BAgg-Dev. Re-generate /
re-push anytime (see [Refreshing the data](#refreshing-the-data)).

## Requirements

| Item | Notes |
|---|---|
| Power BI licence | **Pro** (or Fabric/PPU) trial — activate once at app.powerbi.com. Already working. |
| Browser | Any. No desktop install. |
| Azure CLI | only for re-running the provisioning script (Claude side). |

---

## Choose a path

| | **Path A — Import model** (recommended) | **Path B — Push dataset** (quick) |
|---|---|---|
| Source | upload `B2BAgg-Analytics-data.xlsx` | `B2BAgg Market Data` (already there) |
| DAX measures | ✅ full support (`measures.dax`) | ❌ not supported on push datasets |
| Visuals | implicit + measure-driven | implicit aggregations only (Sum/Avg/Count/Min/Max) |
| Best for | the real demo (shows DAX skill) | a 2-minute preview |

**Recommendation: Path A** — it's the only one that supports the DAX measures,
which are part of the skill story. Path B is a fallback if upload is blocked.

---

## Path A — Import model from the workbook

### A1. Upload the workbook

1. Open https://app.powerbi.com → workspace **B2BAgg-Analytics**.
2. **New → Upload a file → Local file** (or **Upload → Browse this device**),
   pick `powerbi/B2BAgg-Analytics-data.xlsx`, choose **Import** (creates a
   semantic model + a default report you can ignore).
3. You now have a semantic model **B2BAgg-Analytics-data** with two tables:
   `SupplierOffers` (201 rows) and `Orders` (7).

### A2. Set data categories + types (Open data model)

1. On the semantic model → **… → Open data model** (web modeling).
2. Set column types if needed: `Price` = Decimal; `Stock`, `Width`, `Profile`,
   `Diameter`, `LeadDays` = Whole number.
3. Select `SupplierOffers[Region]` → **Properties → Data category = Place**
   (so map visuals geocode the federal-district names). Optionally also set
   `Warehouse` → **City**.

### A3. Add the DAX measures

For each block in [`measures.dax`](measures.dax):

1. In **Open data model**, select the `SupplierOffers` table (or `Orders` for the
   ORDERS section) → **New measure**.
2. Paste the measure expression. Repeat for all measures (the file is grouped by
   report). All measures reference one table — no relationships needed.

### A4. Build the reports

From the semantic model → **Create report → Start from scratch**, then build the
four report pages below. Save as **B2BAgg Market Intelligence** in the workspace.

> Slicer note: there is no Country column in the canonical schema — use **Brand**
> / **Season** / **Diameter** as slicers instead.

#### Report 1 — Regional Demand & Stock
| Element | Config |
|---|---|
| Filled map | Location = `Region` (category Place), saturation = `Total Stock` |
| Bar chart | Axis = `Region`, value = `Total Stock` |
| Card | `Low Stock Alert` |
| Slicers | `Season`, `Brand` |
| Table | `Region`, `Distinct SKU Count`, `Avg Lead Days`, `Total Stock` |

#### Report 2 — Supplier Scorecard
| Element | Config |
|---|---|
| Matrix | Rows = `SupplierName`; values = `Offer Count`, `Fill Rate %`, `Avg Price per Supplier`, `Price Competitiveness %`, `Supplier Stock Rank` |
| Conditional format | `Fill Rate %`: green >80, amber 50–80, red <50 |
| Bar chart | Axis = `SupplierName`, value = `Total Stock` (sort desc) |
| Slicers | `Brand`, `Season` |

#### Report 3 — Top-moving SKUs
| Element | Config |
|---|---|
| Bar chart (H) | Axis = `ProductName`, value = `Total Stock`, legend = `Brand` |
| Page filter | `Stock Rank` ≤ 10 |
| Table | `RawSku`, `SupplierName`, `Stock`, `Best Price`, `Supplier Count per SKU` |
| Card | `Inventory Value` |
| Slicers | `Diameter`, `Season` |

#### Report 4 — Price Spread & Competitiveness
| Element | Config |
|---|---|
| Error/column chart | Axis = `ProductName`; values = `Min Price this Season`, `Avg Price per Supplier`, `Price Spread` |
| Scatter | X = `Fill Rate %`, Y = `Avg Price per Supplier`, size = `Offer Count`, legend = `SupplierName` |
| Cards | `Summer vs Winter Price Ratio`, `Brand Price Premium` |
| Slicers | `Season`, `Brand` |

*(Optional Report 5 — Orders: `Total Revenue`, `Realised Revenue`,
`Avg Order Value`, `Cancellation Rate %`, `Orders by Status`.)*

### A5. Publish / share
The report is already saved in **B2BAgg-Analytics**. For embedding, open it →
**File → Embed report → Website or portal** → copy the embed URL.

---

## Path B — Push dataset (quick preview, no DAX)

The `B2BAgg Market Data` push dataset already holds the real seed data.

1. Workspace **B2BAgg-Analytics** → next to **B2BAgg Market Data** → **Create report**.
2. Build visuals using **implicit aggregations**: drop `Stock` into a chart (set
   to **Sum**), `Price` (**Average**), count rows, etc. Use the pre-aggregated
   `Suppliers` and `Regions` tables for scorecard/region totals.
3. Custom DAX measures are **not** available here — for those, use Path A.

---

## Embed the tile in the Code App (`/insights`)

1. In the service, open the report → **File → Embed report → Website or portal**
   → copy the embed URL.
2. In `apps/buyer-code-app/src/pages/InsightsPage.tsx`, set the `<iframe>` `src`
   to that URL, wrapped in a Fluent UI `Card` (height ~600px).
3. Note: every viewer needs a Power BI Pro licence for embedded tiles (the trial
   covers the demo window).

---

## Refreshing the data

The data is a snapshot (seed-sourced). To refresh:

- **Path A (import):** re-generate + re-upload the workbook:
  ```bash
  python3 powerbi/gen-workbook.py        # rebuilds B2BAgg-Analytics-data.xlsx from data/seed
  # then re-upload in the browser (overwrites the dataset)
  ```
- **Path B (push):** re-run the provisioning script (idempotent — clears + re-pushes):
  ```bash
  python3 scripts/setup-powerbi.py       # DATA_SOURCE=seed (default) | dataverse | mock
  ```

> `setup-powerbi.py` data sources: `seed` (default, from `data/seed/*.csv`, any
> az identity), `dataverse` (live query — needs an **admin** az identity that is
> a member of the Dev org), `mock` (24 bundled rows). Power BI licence currently
> lives on a different identity than the Dataverse admin, so `seed` is the
> reliable headless source.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `UserNotLicensed` from script | az identity lacks Power BI licence | activate Pro/Fabric trial for that user |
| `403` / "not a member of organization" on `DATA_SOURCE=dataverse` | az identity isn't a Dev org member | use default `seed` source, or `az login` as the admin |
| Map shows blank regions | Region not categorized | set `Region` Data category = **Place** |
| Can't add a measure | dataset is the **push** one | use Path A (import model) |
| Embed tile "Content not available" | viewer lacks Pro | assign Pro trial |
